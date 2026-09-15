"""Baseline capture orchestration."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from algocode.application.services.project_service import ProjectService
from algocode.application.services.task_service import TaskService
from algocode.benchmark.environment import compute_environment_hash
from algocode.domain.errors import BaselineBuildFailed, BaselineError, NotFoundError
from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import Baseline, GitRevision, Language, TaskId
from algocode.languages import LanguageRegistry
from algocode.languages.types import BuildProfile, BuildResult
from algocode.ports import ArtifactStore, EventStore
from algocode.storage.sqlite.database import Database
from algocode.storage.sqlite.projections.baseline_projection import BaselineProjection
from algocode.workspace import GitRepository, GitWorkspaceManager


class BaselineService:
    """Prepare an isolated workspace, build it, and persist a baseline."""

    def __init__(
        self,
        event_store: EventStore,
        database: Database,
        task_service: TaskService,
        project_service: ProjectService,
        baseline_projection: BaselineProjection,
        language_registry: LanguageRegistry,
        artifact_store: ArtifactStore,
        workspace_manager_factory: Callable[[GitRepository], GitWorkspaceManager],
    ) -> None:
        self._event_store = event_store
        self._database = database
        self._task_service = task_service
        self._project_service = project_service
        self._baseline_projection = baseline_projection
        self._language_registry = language_registry
        self._artifact_store = artifact_store
        self._workspace_manager_factory = workspace_manager_factory

    async def capture(
        self,
        task_id: TaskId | str,
        *,
        language: Language | str = Language.AUTO,
        source_root: str = ".",
        commands: tuple[tuple[str, ...], ...] = (),
        timeout_seconds: int = 120,
    ) -> Baseline:
        task = await self._task_service.get_task(task_id)
        project = await self._project_service.get(task.project_id)
        repository = await GitRepository.discover(project.root_path)
        revision = await repository.head_revision()
        started_seq = await self._next_seq(str(task.id))
        await self._event_store.append(
            str(task.id),
            started_seq - 1,
            (
                _event(
                    str(task.id),
                    started_seq,
                    EventType.BASELINE_STARTED,
                    {"revision": revision, "project_id": str(project.id)},
                ),
            ),
        )

        workspace_manager = self._workspace_manager_factory(repository)
        try:
            workspace = await workspace_manager.prepare_baseline(str(task.id), revision)
            detected = await self._language_registry.detect(workspace.path)
            requested_language = Language(language)
            if requested_language is Language.AUTO:
                requested_language = (
                    project.language if project.language is not Language.AUTO else Language.AUTO
                )
            selected_language = self._language_registry.resolve_language(
                requested_language,
                detected,
            )
            adapter = self._language_registry.adapter_for(selected_language)
            profile = BuildProfile(
                commands=commands,
                source_root=source_root,
                timeout_seconds=timeout_seconds,
            )
            await adapter.prepare(workspace.path, profile)
            build_result = await adapter.build(workspace.path, profile)
        except Exception as exc:
            failed_seq = started_seq + 1
            await self._event_store.append(
                str(task.id),
                started_seq,
                (
                    _event(
                        str(task.id),
                        failed_seq,
                        EventType.BASELINE_FAILED,
                        {
                            "revision": revision,
                            "reason": str(exc),
                        },
                    ),
                ),
            )
            if isinstance(exc, BaselineError):
                raise
            raise BaselineError(str(exc)) from exc

        output_ref = await self._artifact_store.put(
            build_result.output,
            kind="baseline-build-output",
            mime_type="text/plain",
            metadata={"task_id": str(task.id), "revision": revision},
        )
        metadata_ref = await self._artifact_store.put(
            _build_metadata(build_result),
            kind="baseline-build-result",
            mime_type="application/json",
            metadata={"task_id": str(task.id), "revision": revision},
        )
        if not build_result.succeeded:
            failed_seq = started_seq + 1
            await self._event_store.append(
                str(task.id),
                started_seq,
                (
                    _event(
                        str(task.id),
                        failed_seq,
                        EventType.BASELINE_FAILED,
                        {
                            "revision": revision,
                            "reason": f"baseline build exited with {build_result.exit_code}",
                            "build_result_ref": _artifact_payload(output_ref),
                        },
                        artifact_refs=(output_ref, metadata_ref),
                    ),
                ),
            )
            raise BaselineBuildFailed(f"baseline build exited with code {build_result.exit_code}")

        now = datetime.now(UTC)
        baseline = Baseline(
            id=f"base_{uuid4().hex}",
            task_id=task.id,
            revision=GitRevision(revision),
            snapshot_hash=workspace.base_snapshot_hash,
            environment_hash=compute_environment_hash(workspace.path),
            build_result_ref=output_ref,
            workspace_ref=str(workspace.path),
            created_at=now,
        )
        captured_seq = started_seq + 1
        await self._event_store.append(
            str(task.id),
            started_seq,
            (
                _event(
                    str(task.id),
                    captured_seq,
                    EventType.BASELINE_CAPTURED,
                    {
                        "baseline_id": baseline.id,
                        "revision": baseline.revision.value,
                        "snapshot_hash": baseline.snapshot_hash,
                        "environment_hash": baseline.environment_hash,
                        "build_result_ref": _artifact_payload(output_ref),
                        "correctness_result_ref": None,
                        "benchmark_result_ref": None,
                        "created_at": baseline.created_at.isoformat(),
                        "workspace_ref": str(workspace.path),
                    },
                    artifact_refs=(output_ref, metadata_ref),
                ),
            ),
        )
        return baseline

    async def get(self, baseline_id: str) -> Baseline:
        with self._database.connect() as connection:
            baseline = self._baseline_projection.get(connection, baseline_id)
        if baseline is None:
            raise NotFoundError(f"baseline {baseline_id} was not found")
        return baseline

    async def get_for_task(self, task_id: TaskId | str) -> Baseline | None:
        with self._database.connect() as connection:
            return self._baseline_projection.get_for_task(connection, str(task_id))

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


def _build_metadata(result: BuildResult) -> bytes:
    payload = {
        "language": result.language.value,
        "commands": [list(command) for command in result.commands],
        "run_command": list(result.run_command),
        "executable": str(result.executable) if result.executable is not None else None,
        "exit_code": result.exit_code,
        "duration_seconds": result.duration_seconds,
        "diagnostics": [
            {
                "severity": diagnostic.severity,
                "message": diagnostic.message,
                "file": diagnostic.file,
                "line": diagnostic.line,
                "column": diagnostic.column,
            }
            for diagnostic in result.diagnostics
        ],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
