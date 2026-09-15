"""Benchmark orchestration, sampling, comparison, and persistence."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from algocode.application.services.baseline_service import BaselineService
from algocode.application.services.correctness_service import CorrectnessService
from algocode.application.services.project_service import ProjectService
from algocode.application.services.task_service import TaskService
from algocode.benchmark.engine import (
    collect_interleaved_samples,
    collect_target_samples,
)
from algocode.benchmark.environment import compute_environment_hash
from algocode.benchmark.spec import (
    BenchmarkSpec,
    compute_benchmark_spec_hash,
    compute_comparison_key,
    compute_input_hash,
)
from algocode.benchmark.types import (
    BenchmarkResult,
    BenchmarkSample,
    BenchmarkSummary,
    ComparisonResult,
    compare_summaries,
    summarize_samples,
)
from algocode.domain.errors import BenchmarkError, CorrectnessError, NotFoundError
from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import (
    BenchmarkRun,
    CorrectnessStatus,
    Language,
    TaskId,
)
from algocode.languages import LanguageRegistry
from algocode.languages.types import BuildProfile, BuildResult
from algocode.ports import ArtifactStore, EventStore
from algocode.runtime.locks import FileResourceLock
from algocode.storage.sqlite.database import Database
from algocode.storage.sqlite.projections.benchmark_projection import BenchmarkProjection
from algocode.workspace import GitRepository


class BenchmarkService:
    """Run reproducible, interleaved baseline and candidate benchmarks."""

    def __init__(
        self,
        event_store: EventStore,
        database: Database,
        task_service: TaskService,
        project_service: ProjectService,
        baseline_service: BaselineService,
        correctness_service: CorrectnessService,
        benchmark_projection: BenchmarkProjection,
        language_registry: LanguageRegistry,
        artifact_store: ArtifactStore,
        lock_root: str | Path,
    ) -> None:
        self._event_store = event_store
        self._database = database
        self._task_service = task_service
        self._project_service = project_service
        self._baseline_service = baseline_service
        self._correctness_service = correctness_service
        self._benchmark_projection = benchmark_projection
        self._language_registry = language_registry
        self._artifact_store = artifact_store
        self._lock_root = Path(lock_root).expanduser()

    async def run_baseline(
        self,
        task_id: TaskId | str,
        spec: BenchmarkSpec,
        *,
        build_profile: BuildProfile | None = None,
        language: Language | str = Language.AUTO,
    ) -> tuple[BenchmarkRun, BenchmarkResult]:
        task = await self._task_service.get_task(task_id)
        baseline = await self._baseline_service.get_for_task(task.id)
        if baseline is None or baseline.workspace_ref is None:
            raise BenchmarkError("baseline workspace is not available")
        if baseline.correctness_result_ref is None:
            raise BenchmarkError("baseline correctness must pass before benchmark")
        workspace = Path(baseline.workspace_ref)
        return await self._run_single(
            task.id,
            spec,
            target_kind="baseline",
            target_id=baseline.id,
            workspace=workspace,
            build_profile=build_profile,
            language=language,
            correctness_result_id=None,
        )

    async def run_candidate(
        self,
        task_id: TaskId | str,
        candidate_id: str,
        workspace_ref: str | Path,
        correctness_result_id: str,
        spec: BenchmarkSpec,
        *,
        build_profile: BuildProfile | None = None,
        language: Language | str = Language.AUTO,
    ) -> tuple[BenchmarkRun, BenchmarkResult, ComparisonResult]:
        task = await self._task_service.get_task(task_id)
        baseline = await self._baseline_service.get_for_task(task.id)
        if baseline is None or baseline.workspace_ref is None:
            raise BenchmarkError("baseline workspace is not available")
        if baseline.correctness_result_ref is None:
            raise BenchmarkError("baseline correctness must pass before benchmark")
        correctness = await self._correctness_service.get(correctness_result_id)
        if (
            correctness.status is not CorrectnessStatus.PASSED
            or correctness.target_kind != "candidate"
            or correctness.target_id != candidate_id
        ):
            raise CorrectnessError("candidate correctness must pass before benchmark")

        baseline_workspace = Path(baseline.workspace_ref)
        candidate_workspace = Path(workspace_ref)
        if not candidate_workspace.exists():
            raise BenchmarkError(f"candidate workspace does not exist: {candidate_workspace}")
        environment_hash = compute_environment_hash(baseline_workspace)
        candidate_environment_hash = compute_environment_hash(candidate_workspace)
        if candidate_environment_hash != environment_hash:
            raise BenchmarkError("candidate environment does not match the baseline environment")
        comparison_key = compute_comparison_key(
            spec_hash=compute_benchmark_spec_hash(spec),
            input_hash=compute_input_hash(spec),
            environment_hash=environment_hash,
        )
        baseline_snapshot = await GitRepository.discover(baseline_workspace)
        baseline_hash = (await baseline_snapshot.capture_snapshot(baseline_workspace)).snapshot_hash
        candidate_repository = await GitRepository.discover(candidate_workspace)
        candidate_hash = (
            await candidate_repository.capture_snapshot(candidate_workspace)
        ).snapshot_hash
        run_id = f"bench_{uuid4().hex}"
        started_seq = await self._next_seq(str(task.id))
        await self._event_store.append(
            str(task.id),
            started_seq - 1,
            (
                _event(
                    str(task.id),
                    started_seq,
                    EventType.EXPERIMENT_CREATED,
                    {
                        "run_id": run_id,
                        "target_kind": "candidate",
                        "target_id": candidate_id,
                        "workspace_ref": str(candidate_workspace),
                        "spec_hash": compute_benchmark_spec_hash(spec),
                        "input_hash": compute_input_hash(spec),
                        "environment_hash": environment_hash,
                        "comparison_key": comparison_key,
                        "correctness_result_id": correctness_result_id,
                    },
                ),
            ),
        )

        try:
            async with FileResourceLock(
                self._lock_root,
                f"benchmark:{environment_hash}",
            ):
                baseline_adapter, baseline_spec = await self._prepare_workspace(
                    baseline_workspace,
                    spec,
                    build_profile,
                    language,
                )
                candidate_adapter, candidate_spec = await self._prepare_workspace(
                    candidate_workspace,
                    spec,
                    build_profile,
                    language,
                )
                samples = await collect_interleaved_samples(
                    baseline_workspace,
                    candidate_workspace,
                    baseline_spec,
                    candidate_spec,
                    baseline_id=baseline.id,
                    candidate_id=candidate_id,
                    sandbox_runner=self._language_registry.sandbox_runner,
                )
                baseline_summary = summarize_samples(
                    samples,
                    metric=spec.metric,
                )
                candidate_samples = tuple(
                    sample for sample in samples if sample.target_kind == "candidate"
                )
                candidate_summary = summarize_samples(
                    candidate_samples,
                    metric=spec.metric,
                )
                if baseline_summary is None or candidate_summary is None:
                    raise BenchmarkError("benchmark did not produce measured samples")
                all_valid = all(sample.valid for sample in samples if sample.phase == "measured")
                comparison = compare_summaries(
                    baseline_run_id=run_id,
                    candidate_run_id=run_id,
                    baseline_id=baseline.id,
                    candidate_id=candidate_id,
                    comparison_key=comparison_key,
                    baseline=baseline_summary,
                    candidate=candidate_summary,
                    direction=spec.direction,
                    max_variation_percent=spec.max_variation_percent,
                )
        except Exception as exc:
            failed_seq = started_seq + 1
            await self._event_store.append(
                str(task.id),
                started_seq,
                (
                    _event(
                        str(task.id),
                        failed_seq,
                        EventType.EXPERIMENT_FAILED,
                        {"run_id": run_id, "reason": str(exc)},
                    ),
                ),
            )
            if isinstance(exc, (BenchmarkError, CorrectnessError)):
                raise
            raise BenchmarkError(str(exc)) from exc

        result = BenchmarkResult(
            target_kind="candidate",
            target_id=candidate_id,
            workspace_ref=str(candidate_workspace),
            spec_hash=compute_benchmark_spec_hash(spec),
            input_hash=compute_input_hash(spec),
            environment_hash=environment_hash,
            comparison_key=comparison_key,
            workspace_hash=candidate_hash,
            samples=candidate_samples,
            summary=candidate_summary,
            valid=all_valid,
            message="" if all_valid else "one or more measured samples were invalid",
        )
        result_bytes = _serialize_result(
            result,
            baseline_summary=baseline_summary,
            candidate_summary=candidate_summary,
            comparison=comparison,
            all_samples=samples,
            baseline_workspace_hash=baseline_hash,
        )
        comparison_bytes = _serialize_comparison(comparison)
        result_ref = await self._artifact_store.put(
            result_bytes,
            kind="benchmark-result",
            mime_type="application/json",
            metadata={"task_id": str(task.id), "comparison_key": comparison_key},
        )
        comparison_ref = await self._artifact_store.put(
            comparison_bytes,
            kind="benchmark-comparison",
            mime_type="application/json",
            metadata={"task_id": str(task.id), "comparison_key": comparison_key},
        )
        await self._event_store.append(
            str(task.id),
            started_seq,
            (
                _samples_event(
                    str(task.id),
                    started_seq + 1,
                    run_id=run_id,
                    target_kind="candidate",
                    target_id=candidate_id,
                    result_ref=result_ref,
                    samples=samples,
                ),
                _event(
                    str(task.id),
                    started_seq + 2,
                    EventType.COMPARISON_PRODUCED,
                    {
                        "run_id": run_id,
                        "comparison_ref": _artifact_payload(comparison_ref),
                        "comparison": _comparison_payload(comparison),
                    },
                    artifact_refs=(comparison_ref,),
                ),
                _event(
                    str(task.id),
                    started_seq + 3,
                    EventType.EXPERIMENT_COMPLETED,
                    {"run_id": run_id},
                ),
            ),
        )
        run = await self.get(run_id)
        return run, result, comparison

    async def get(self, run_id: str) -> BenchmarkRun:
        with self._database.connect() as connection:
            run = self._benchmark_projection.get(connection, run_id)
        if run is None:
            raise NotFoundError(f"benchmark run {run_id} was not found")
        return run

    async def list_for_task(self, task_id: TaskId | str) -> list[BenchmarkRun]:
        with self._database.connect() as connection:
            return self._benchmark_projection.list_for_task(connection, str(task_id))

    async def list_all(self) -> list[BenchmarkRun]:
        with self._database.connect() as connection:
            return self._benchmark_projection.list_all(connection)

    async def read_comparison(self, run: BenchmarkRun) -> dict | None:
        if run.comparison_ref is None:
            return None
        data = await self._artifact_store.read_bytes(run.comparison_ref)
        return json.loads(data)

    async def read_result(self, run: BenchmarkRun) -> dict:
        if run.result_ref is None:
            raise BenchmarkError(f"benchmark {run.id} has no result artifact")
        data = await self._artifact_store.read_bytes(run.result_ref)
        return json.loads(data)

    async def _run_single(
        self,
        task_id: TaskId,
        spec: BenchmarkSpec,
        *,
        target_kind: str,
        target_id: str,
        workspace: Path,
        build_profile: BuildProfile | None,
        language: Language | str,
        correctness_result_id: str | None,
    ) -> tuple[BenchmarkRun, BenchmarkResult]:
        environment_hash = compute_environment_hash(workspace)
        spec_hash = compute_benchmark_spec_hash(spec)
        input_hash = compute_input_hash(spec)
        comparison_key = compute_comparison_key(
            spec_hash=spec_hash,
            input_hash=input_hash,
            environment_hash=environment_hash,
        )
        repository = await GitRepository.discover(workspace)
        workspace_hash = (await repository.capture_snapshot(workspace)).snapshot_hash
        run_id = f"bench_{uuid4().hex}"
        started_seq = await self._next_seq(str(task_id))
        await self._event_store.append(
            str(task_id),
            started_seq - 1,
            (
                _event(
                    str(task_id),
                    started_seq,
                    EventType.EXPERIMENT_CREATED,
                    {
                        "run_id": run_id,
                        "target_kind": target_kind,
                        "target_id": target_id,
                        "workspace_ref": str(workspace),
                        "spec_hash": spec_hash,
                        "input_hash": input_hash,
                        "environment_hash": environment_hash,
                        "comparison_key": comparison_key,
                        "correctness_result_id": correctness_result_id,
                    },
                ),
            ),
        )
        try:
            async with FileResourceLock(
                self._lock_root,
                f"benchmark:{environment_hash}",
            ):
                _, prepared_spec = await self._prepare_workspace(
                    workspace,
                    spec,
                    build_profile,
                    language,
                )
                samples = await collect_target_samples(
                    workspace,
                    prepared_spec,
                    target_kind=target_kind,
                    target_id=target_id,
                    sandbox_runner=self._language_registry.sandbox_runner,
                )
                summary = summarize_samples(samples, metric=spec.metric)
                if summary is None:
                    raise BenchmarkError("benchmark did not produce measured samples")
                valid = all(sample.valid for sample in samples if sample.phase == "measured")
        except Exception as exc:
            await self._event_store.append(
                str(task_id),
                started_seq,
                (
                    _event(
                        str(task_id),
                        started_seq + 1,
                        EventType.EXPERIMENT_FAILED,
                        {"run_id": run_id, "reason": str(exc)},
                    ),
                ),
            )
            if isinstance(exc, BenchmarkError):
                raise
            raise BenchmarkError(str(exc)) from exc
        result = BenchmarkResult(
            target_kind=target_kind,
            target_id=target_id,
            workspace_ref=str(workspace),
            spec_hash=spec_hash,
            input_hash=input_hash,
            environment_hash=environment_hash,
            comparison_key=comparison_key,
            workspace_hash=workspace_hash,
            samples=samples,
            summary=summary,
            valid=valid,
            message="" if valid else "one or more measured samples were invalid",
        )
        result_bytes = _serialize_result(
            result,
            baseline_summary=summary if target_kind == "baseline" else None,
            candidate_summary=None,
            comparison=None,
            all_samples=samples,
            baseline_workspace_hash=workspace_hash if target_kind == "baseline" else None,
        )
        result_ref = await self._artifact_store.put(
            result_bytes,
            kind="benchmark-result",
            mime_type="application/json",
            metadata={"task_id": str(task_id), "comparison_key": comparison_key},
        )
        await self._event_store.append(
            str(task_id),
            started_seq,
            (
                _samples_event(
                    str(task_id),
                    started_seq + 1,
                    run_id=run_id,
                    target_kind=target_kind,
                    target_id=target_id,
                    result_ref=result_ref,
                    samples=samples,
                ),
                _event(
                    str(task_id),
                    started_seq + 2,
                    EventType.EXPERIMENT_COMPLETED,
                    {"run_id": run_id},
                ),
            ),
        )
        return await self.get(run_id), result

    async def _prepare_workspace(
        self,
        workspace: Path,
        spec: BenchmarkSpec,
        build_profile: BuildProfile | None,
        language: Language | str,
    ) -> tuple[object, BenchmarkSpec]:
        detected = await self._language_registry.detect(workspace)
        selected = self._language_registry.resolve_language(language, detected)
        adapter = self._language_registry.adapter_for(selected)
        profile = build_profile or BuildProfile(source_root=spec.source_root)
        await adapter.prepare(workspace, profile)
        build_result: BuildResult = await adapter.build(workspace, profile)
        if not build_result.succeeded:
            raise BenchmarkError(f"benchmark build exited with {build_result.exit_code}")
        run_command = spec.run_command or build_result.run_command
        if not run_command and build_result.executable is not None:
            run_command = (str(build_result.executable),)
        if not run_command:
            raise BenchmarkError("no benchmark run command was configured or discovered")
        return adapter, spec.model_copy(update={"run_command": tuple(run_command)})

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


def _samples_event(
    aggregate_id: str,
    seq: int,
    *,
    run_id: str,
    target_kind: str,
    target_id: str,
    result_ref,
    samples: tuple[BenchmarkSample, ...],
) -> EventEnvelope:
    return _event(
        aggregate_id,
        seq,
        EventType.BENCHMARK_SAMPLES_CAPTURED,
        {
            "run_id": run_id,
            "target_kind": target_kind,
            "target_id": target_id,
            "result_ref": _artifact_payload(result_ref),
            "samples": [_sample_payload(sample) for sample in samples],
        },
        artifact_refs=(result_ref,),
    )


def _sample_payload(sample: BenchmarkSample) -> dict[str, object]:
    return {
        "target_kind": sample.target_kind,
        "target_id": sample.target_id,
        "phase": sample.phase,
        "index": sample.index,
        "metric": sample.metric.value,
        "value": sample.value,
        "duration_seconds": sample.duration_seconds,
        "exit_code": sample.exit_code,
        "valid": sample.valid,
        "message": sample.message,
    }


def _summary_payload(summary: BenchmarkSummary | None) -> dict[str, float] | None:
    if summary is None:
        return None
    return {
        "count": summary.count,
        "median": summary.median,
        "minimum": summary.minimum,
        "maximum": summary.maximum,
        "mean": summary.mean,
        "stddev": summary.stddev,
        "variation_percent": summary.variation_percent,
    }


def _comparison_payload(comparison: ComparisonResult) -> dict[str, object]:
    return {
        "baseline_run_id": comparison.baseline_run_id,
        "candidate_run_id": comparison.candidate_run_id,
        "baseline_id": comparison.baseline_id,
        "candidate_id": comparison.candidate_id,
        "comparison_key": comparison.comparison_key,
        "baseline_median": comparison.baseline_median,
        "candidate_median": comparison.candidate_median,
        "improvement_percent": comparison.improvement_percent,
        "valid": comparison.valid,
        "reason": comparison.reason,
    }


def _serialize_result(
    result: BenchmarkResult,
    *,
    baseline_summary: BenchmarkSummary | None,
    candidate_summary: BenchmarkSummary | None,
    comparison: ComparisonResult | None,
    all_samples: tuple[BenchmarkSample, ...],
    baseline_workspace_hash: str | None,
) -> bytes:
    payload = {
        "target_kind": result.target_kind,
        "target_id": result.target_id,
        "workspace_ref": result.workspace_ref,
        "workspace_hash": result.workspace_hash,
        "baseline_workspace_hash": baseline_workspace_hash,
        "spec_hash": result.spec_hash,
        "input_hash": result.input_hash,
        "environment_hash": result.environment_hash,
        "comparison_key": result.comparison_key,
        "valid": result.valid,
        "message": result.message,
        "summary": _summary_payload(result.summary),
        "baseline_summary": _summary_payload(baseline_summary),
        "candidate_summary": _summary_payload(candidate_summary),
        "comparison": None if comparison is None else _comparison_payload(comparison),
        "samples": [_sample_payload(sample) for sample in all_samples],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")


def _serialize_comparison(comparison: ComparisonResult) -> bytes:
    return json.dumps(
        _comparison_payload(comparison),
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")


def _artifact_payload(ref) -> dict[str, str]:
    return {"uri": ref.uri, "sha256": ref.sha256}
