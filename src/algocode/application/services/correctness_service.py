"""Correctness orchestration service."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from uuid import uuid4

from algocode.application.services.baseline_service import BaselineService
from algocode.application.services.project_service import ProjectService
from algocode.application.services.task_service import TaskService
from algocode.correctness.protected import find_protected_changes, make_protected_failure
from algocode.correctness.spec import CorrectnessSpec, compute_spec_hash
from algocode.correctness.types import CaseResult, CorrectnessResult
from algocode.domain.errors import CorrectnessError, NotFoundError
from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import (
    CorrectnessRun,
    CorrectnessStatus,
    FailureKind,
    Language,
    TaskId,
)
from algocode.languages import LanguageRegistry
from algocode.languages.types import BuildProfile, BuildResult
from algocode.ports import ArtifactStore, EventStore
from algocode.storage.sqlite.database import Database
from algocode.storage.sqlite.projections.correctness_projection import CorrectnessProjection


class CorrectnessService:
    """Run and replay correctness suites against persisted workspaces."""

    def __init__(
        self,
        event_store: EventStore,
        database: Database,
        task_service: TaskService,
        project_service: ProjectService,
        baseline_service: BaselineService,
        correctness_projection: CorrectnessProjection,
        language_registry: LanguageRegistry,
        artifact_store: ArtifactStore,
    ) -> None:
        self._event_store = event_store
        self._database = database
        self._task_service = task_service
        self._project_service = project_service
        self._baseline_service = baseline_service
        self._correctness_projection = correctness_projection
        self._language_registry = language_registry
        self._artifact_store = artifact_store

    async def run_baseline(
        self,
        task_id: TaskId | str,
        spec: CorrectnessSpec,
        *,
        build_profile: BuildProfile | None = None,
        language: Language | str = Language.AUTO,
    ) -> tuple[CorrectnessRun, CorrectnessResult]:
        task = await self._task_service.get_task(task_id)
        baseline = await self._baseline_service.get_for_task(task.id)
        if baseline is None:
            raise CorrectnessError("baseline must be captured before correctness")
        if baseline.workspace_ref is None:
            raise CorrectnessError("baseline does not reference a persisted workspace")
        return await self.run_target(
            task.id,
            spec,
            target_kind="baseline",
            target_id=baseline.id,
            workspace_ref=baseline.workspace_ref,
            build_profile=build_profile,
            language=language,
        )

    async def run_target(
        self,
        task_id: TaskId | str,
        spec: CorrectnessSpec,
        *,
        target_kind: str,
        target_id: str,
        workspace_ref: str | Path,
        build_profile: BuildProfile | None = None,
        language: Language | str = Language.AUTO,
        changed_paths: tuple[str, ...] = (),
        record_candidate_status: bool = True,
    ) -> tuple[CorrectnessRun, CorrectnessResult]:
        if target_kind not in {"baseline", "candidate"}:
            raise ValueError("target_kind must be baseline or candidate")
        task = await self._task_service.get_task(task_id)
        workspace = Path(workspace_ref)
        if not workspace.exists():
            raise CorrectnessError(f"target workspace does not exist: {workspace}")
        project = await self._project_service.get(task.project_id)
        detected = await self._language_registry.detect(workspace)
        selected_language = self._language_registry.resolve_language(
            project.language if language == Language.AUTO else language,
            detected,
        )
        adapter = self._language_registry.adapter_for(selected_language)
        spec_hash = compute_spec_hash(spec)
        result_id = f"corr_{uuid4().hex}"
        spec_bytes = json.dumps(
            spec.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
        spec_ref = await self._artifact_store.put(
            spec_bytes,
            kind="correctness-spec",
            mime_type="application/json",
            metadata={"task_id": str(task.id), "spec_hash": spec_hash},
        )
        started_seq = await self._next_seq(str(task.id))
        await self._event_store.append(
            str(task.id),
            started_seq - 1,
            (
                _event(
                    str(task.id),
                    started_seq,
                    EventType.CORRECTNESS_STARTED,
                    {
                        "result_id": result_id,
                        "target_kind": target_kind,
                        "target_id": target_id,
                        "workspace_ref": str(workspace),
                        "spec_hash": spec_hash,
                        "spec_ref": _artifact_payload(spec_ref),
                        "record_candidate_status": record_candidate_status,
                    },
                    artifact_refs=(spec_ref,),
                ),
            ),
        )

        prepared_spec = spec
        try:
            protected_changes = find_protected_changes(
                changed_paths,
                spec.protected_files,
            )
            if protected_changes:
                correctness_result = make_protected_failure(protected_changes)
            else:
                profile = build_profile or BuildProfile(source_root=spec.source_root)
                await adapter.prepare(workspace, profile)
                build_result = await adapter.build(workspace, profile)
                if not build_result.succeeded:
                    correctness_result = _build_failure_result(build_result)
                else:
                    run_command = spec.run_command or build_result.run_command
                    if not run_command and build_result.executable is not None:
                        run_command = (str(build_result.executable),)
                    if not run_command:
                        correctness_result = _configuration_failure(
                            "no run command was configured or discovered"
                        )
                    else:
                        prepared_spec = spec.model_copy(update={"run_command": tuple(run_command)})
                        correctness_result = await adapter.run_correctness(
                            workspace,
                            prepared_spec,
                        )
        except Exception as exc:
            correctness_result = CorrectnessResult(
                passed=False,
                status=CorrectnessStatus.FAILED.value,
                duration_seconds=0.0,
                failure_kind=FailureKind.PROCESS_CRASH,
                message=str(exc),
                cases=(
                    CaseResult(
                        case_id="execution",
                        passed=False,
                        duration_seconds=0.0,
                        failure_kind=FailureKind.PROCESS_CRASH,
                        message=str(exc),
                    ),
                ),
            )

        result_bytes = _serialize_result(correctness_result, prepared_spec, spec_hash)
        result_ref = await self._artifact_store.put(
            result_bytes,
            kind="correctness-result",
            mime_type="application/json",
            metadata={"task_id": str(task.id), "spec_hash": spec_hash},
        )
        artifacts = [spec_ref, result_ref]
        failure_ref = None
        if not correctness_result.passed:
            failure_ref = await self._artifact_store.put(
                result_bytes,
                kind="correctness-failure",
                mime_type="application/json",
                metadata={"task_id": str(task.id), "spec_hash": spec_hash},
            )
            artifacts.append(failure_ref)

        completed_event = (
            EventType.CORRECTNESS_PASSED
            if correctness_result.passed
            else EventType.CORRECTNESS_FAILED
        )
        await self._event_store.append(
            str(task.id),
            started_seq,
            (
                _event(
                    str(task.id),
                    started_seq + 1,
                    completed_event,
                    {
                        "result_id": result_id,
                        "target_kind": target_kind,
                        "target_id": target_id,
                        "status": correctness_result.status,
                        "failure_kind": (
                            correctness_result.failure_kind.value
                            if correctness_result.failure_kind is not None
                            else None
                        ),
                        "message": correctness_result.message,
                        "result_ref": _artifact_payload(result_ref),
                        "failure_ref": (
                            _artifact_payload(failure_ref) if failure_ref is not None else None
                        ),
                        "record_candidate_status": record_candidate_status,
                    },
                    artifact_refs=tuple(artifacts),
                ),
            ),
        )
        run = await self.get(result_id)
        return run, correctness_result

    async def replay(
        self,
        result_id: str,
        *,
        build_profile: BuildProfile | None = None,
        language: Language | str = Language.AUTO,
    ) -> tuple[CorrectnessRun, CorrectnessResult]:
        previous = await self.get(result_id)
        spec_bytes = await self._artifact_store.read_bytes(previous.spec_ref)
        spec = CorrectnessSpec.model_validate(json.loads(spec_bytes))
        return await self.run_target(
            previous.task_id,
            spec,
            target_kind=previous.target_kind,
            target_id=previous.target_id,
            workspace_ref=previous.workspace_ref,
            build_profile=build_profile,
            language=language,
        )

    async def get(self, result_id: str) -> CorrectnessRun:
        with self._database.connect() as connection:
            run = self._correctness_projection.get(connection, result_id)
        if run is None:
            raise NotFoundError(f"correctness run {result_id} was not found")
        return run

    async def list_for_task(self, task_id: TaskId | str) -> list[CorrectnessRun]:
        with self._database.connect() as connection:
            return self._correctness_projection.list_for_task(connection, str(task_id))

    async def _next_seq(self, aggregate_id: str) -> int:
        events = await self._event_store.read(aggregate_id)
        return events[-1].seq + 1 if events else 1


def _event(
    aggregate_id: str,
    seq: int,
    event_type: EventType,
    payload: dict[str, object],
    *,
    artifact_refs=(),
) -> EventEnvelope:
    return EventEnvelope(
        id=f"evt_{uuid4().hex}",
        aggregate_id=aggregate_id,
        seq=seq,
        type=event_type,
        payload=payload,
        artifact_refs=tuple(artifact_refs),
    )


def _artifact_payload(ref) -> dict[str, str]:
    return {"uri": ref.uri, "sha256": ref.sha256}


def _build_failure_result(build_result: BuildResult) -> CorrectnessResult:
    return CorrectnessResult(
        passed=False,
        status=CorrectnessStatus.FAILED.value,
        duration_seconds=build_result.duration_seconds,
        failure_kind=FailureKind.PROCESS_CRASH,
        message=f"correctness build exited with {build_result.exit_code}",
        cases=(
            CaseResult(
                case_id="build",
                passed=False,
                duration_seconds=build_result.duration_seconds,
                failure_kind=FailureKind.PROCESS_CRASH,
                message="correctness build failed",
                actual_output=build_result.stdout,
                actual_stderr=build_result.stderr,
                actual_exit_code=build_result.exit_code,
            ),
        ),
    )


def _configuration_failure(message: str) -> CorrectnessResult:
    return CorrectnessResult(
        passed=False,
        status=CorrectnessStatus.INCONCLUSIVE.value,
        duration_seconds=0.0,
        failure_kind=FailureKind.INCONCLUSIVE,
        message=message,
        cases=(
            CaseResult(
                case_id="configuration",
                passed=False,
                duration_seconds=0.0,
                failure_kind=FailureKind.INCONCLUSIVE,
                message=message,
            ),
        ),
    )


def _serialize_result(
    result: CorrectnessResult,
    spec: CorrectnessSpec,
    spec_hash: str,
) -> bytes:
    payload = {
        "passed": result.passed,
        "status": result.status,
        "duration_seconds": result.duration_seconds,
        "failure_kind": None if result.failure_kind is None else result.failure_kind.value,
        "message": result.message,
        "passed_cases": result.passed_cases,
        "failed_cases": result.failed_cases,
        "spec_hash": spec_hash,
        "spec": spec.model_dump(mode="json"),
        "cases": [_serialize_case(case) for case in result.cases],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")


def _serialize_case(case: CaseResult) -> dict[str, object]:
    return {
        "case_id": case.case_id,
        "passed": case.passed,
        "duration_seconds": case.duration_seconds,
        "failure_kind": None if case.failure_kind is None else case.failure_kind.value,
        "message": case.message,
        "input_base64": base64.b64encode(case.input).decode("ascii"),
        "input_hash": case.input_hash,
        "actual_output_base64": base64.b64encode(case.actual_output).decode("ascii"),
        "expected_output_base64": (
            base64.b64encode(case.expected_output).decode("ascii")
            if case.expected_output is not None
            else None
        ),
        "oracle_output_base64": (
            base64.b64encode(case.oracle_output).decode("ascii")
            if case.oracle_output is not None
            else None
        ),
        "actual_stderr_base64": base64.b64encode(case.actual_stderr).decode("ascii"),
        "actual_exit_code": case.actual_exit_code,
        "expected_exit_code": case.expected_exit_code,
        "oracle_exit_code": case.oracle_exit_code,
        "seed": case.seed,
        "generator_hash": case.generator_hash,
    }
