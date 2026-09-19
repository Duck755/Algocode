"""Acceptance and decision service."""

from __future__ import annotations

import statistics
from datetime import UTC, datetime
from uuid import uuid4

from algocode.application.services.benchmark_service import BenchmarkService
from algocode.application.services.candidate_service import CandidateService
from algocode.application.services.correctness_service import CorrectnessService
from algocode.application.services.task_service import TaskService
from algocode.config.model import AcceptancePolicyConfig
from algocode.domain.errors import DecisionError
from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import (
    ArtifactRef,
    BenchmarkStatus,
    CandidateId,
    CorrectnessStatus,
    Decision,
    DecisionId,
    DecisionOutcome,
    TaskId,
    new_decision_id,
)
from algocode.ports import EventStore
from algocode.storage.sqlite.database import Database
from algocode.storage.sqlite.projections.decision_projection import DecisionProjection


class DecisionService:
    """Record decisions without modifying the user workspace."""

    def __init__(
        self,
        event_store: EventStore,
        database: Database,
        task_service: TaskService,
        candidate_service: CandidateService,
        correctness_service: CorrectnessService,
        benchmark_service: BenchmarkService,
        decision_projection: DecisionProjection,
        acceptance_policy: AcceptancePolicyConfig | None = None,
    ) -> None:
        self._event_store = event_store
        self._database = database
        self._task_service = task_service
        self._candidate_service = candidate_service
        self._correctness_service = correctness_service
        self._benchmark_service = benchmark_service
        self._decision_projection = decision_projection
        self._acceptance_policy = acceptance_policy or AcceptancePolicyConfig()

    async def accept(
        self,
        task_id: TaskId | str,
        candidate_id: CandidateId | str,
        *,
        reason: str = "",
    ) -> Decision:
        task = await self._task_service.get_task(task_id)
        candidate = await self._candidate_service.get(candidate_id)
        if candidate.task_id != task.id:
            raise DecisionError("candidate does not belong to the task")
        correctness_runs = await self._correctness_service.list_for_task(task.id)
        correctness = next(
            (
                run
                for run in correctness_runs
                if run.target_kind == "candidate" and run.target_id == str(candidate.id)
            ),
            None,
        )
        if self._acceptance_policy.require_correctness and (
            correctness is None or correctness.status is not CorrectnessStatus.PASSED
        ):
            raise DecisionError("candidate correctness must pass before acceptance")
        if correctness is None or correctness.result_ref is None:
            raise DecisionError("candidate correctness has no result artifact")
        evidence: list[ArtifactRef] = [correctness.result_ref]

        benchmark_runs = await self._benchmark_service.list_for_task(task.id)
        benchmark = next(
            (
                run
                for run in benchmark_runs
                if run.target_kind == "candidate" and run.target_id == str(candidate.id)
            ),
            None,
        )
        if (
            benchmark is None
            or benchmark.status is not BenchmarkStatus.COMPLETED
            or benchmark.result_ref is None
            or benchmark.comparison_ref is None
        ):
            raise DecisionError("valid candidate benchmark evidence is required before acceptance")
        benchmark_result = await self._benchmark_service.read_result(benchmark)
        comparison = await self._benchmark_service.read_comparison(benchmark)
        if comparison is None or comparison.get("valid") is not True:
            raise DecisionError("candidate benchmark comparison is invalid")
        self._validate_acceptance_thresholds(benchmark_result, comparison)
        evidence.extend((benchmark.result_ref, benchmark.comparison_ref))

        decision = Decision(
            id=new_decision_id(),
            task_id=task.id,
            candidate_id=candidate.id,
            outcome=DecisionOutcome.ACCEPTED,
            reason=reason or "correctness and benchmark evidence passed acceptance policy",
            evidence_refs=evidence,
            decided_at=datetime.now(UTC),
        )
        seq = await self._next_seq(str(task.id))
        await self._event_store.append(
            str(task.id),
            seq - 1,
            (
                _event(
                    str(task.id),
                    seq,
                    EventType.DECISION_MADE,
                    {
                        "decision_id": str(decision.id),
                        "candidate_id": str(candidate.id),
                        "outcome": decision.outcome.value,
                        "reason": decision.reason,
                        "evidence_refs": [_artifact_payload(ref) for ref in evidence],
                    },
                ),
            ),
        )
        return await self.get(decision.id)

    def _validate_acceptance_thresholds(
        self,
        benchmark_result: dict[str, object],
        comparison: dict[str, object],
    ) -> None:
        improvement = float(comparison.get("improvement_percent", 0.0))
        if improvement < self._acceptance_policy.min_median_improvement_percent:
            raise DecisionError(
                f"candidate improvement is below the acceptance threshold: {improvement:.6f}%"
            )
        max_variation = self._acceptance_policy.max_variation_percent
        if max_variation is not None:
            for key in ("baseline_summary", "candidate_summary"):
                summary = benchmark_result.get(key)
                if isinstance(summary, dict):
                    variation = float(summary.get("variation_percent", 0.0))
                    if variation > max_variation:
                        raise DecisionError(
                            f"{key} variation exceeds acceptance threshold: {variation:.6f}%"
                        )
        if self._acceptance_policy.require_statistically_significant:
            statistically_significant = comparison.get("statistically_significant")
            if statistically_significant is False:
                p_value = comparison.get("p_value")
                detail = f" p_value={p_value:.4f}" if isinstance(p_value, (int, float)) else ""
                raise DecisionError(
                    f"candidate improvement is not statistically significant{detail}"
                )
            if statistically_significant is None and "p_value" in comparison:
                raise DecisionError("candidate comparison has no statistical significance evidence")
        for metric, threshold in (
            ("peak_memory", self._acceptance_policy.max_peak_memory_regression_percent),
            ("compile_time", self._acceptance_policy.max_compile_time_regression_percent),
        ):
            if threshold is None:
                continue
            regression = _metric_regression_percent(benchmark_result, metric)
            if regression is not None and regression > threshold:
                raise DecisionError(
                    f"{metric} regression exceeds acceptance threshold: {regression:.6f}%"
                )

    async def get(self, decision_id: DecisionId | str) -> Decision:
        with self._database.connect() as connection:
            decision = self._decision_projection.get(connection, str(decision_id))
        if decision is None:
            raise DecisionError(f"decision {decision_id} was not found")
        return decision

    async def get_for_candidate(self, candidate_id: CandidateId | str) -> Decision | None:
        with self._database.connect() as connection:
            return self._decision_projection.get_for_candidate(connection, str(candidate_id))

    async def _next_seq(self, aggregate_id: str) -> int:
        events = await self._event_store.read(aggregate_id)
        return events[-1].seq + 1 if events else 1


def _metric_regression_percent(
    benchmark_result: dict[str, object],
    metric: str,
) -> float | None:
    samples = benchmark_result.get("samples")
    if not isinstance(samples, list):
        return None
    baseline: list[float] = []
    candidate: list[float] = []
    for sample in samples:
        if not isinstance(sample, dict) or sample.get("metric") != metric:
            continue
        if sample.get("phase") != "measured" or sample.get("valid") is not True:
            continue
        value = sample.get("value")
        if not isinstance(value, int | float):
            continue
        if sample.get("target_kind") == "baseline":
            baseline.append(float(value))
        elif sample.get("target_kind") == "candidate":
            candidate.append(float(value))
    if not baseline or not candidate or statistics.median(baseline) == 0:
        return None
    baseline_median = statistics.median(baseline)
    candidate_median = statistics.median(candidate)
    return (candidate_median - baseline_median) / baseline_median * 100.0


def _event(
    aggregate_id: str,
    seq: int,
    event_type: EventType,
    payload: dict[str, object],
) -> EventEnvelope:
    return EventEnvelope(
        id=f"evt_{uuid4().hex}",
        aggregate_id=aggregate_id,
        seq=seq,
        type=event_type,
        payload=payload,
    )


def _artifact_payload(ref: ArtifactRef) -> dict[str, str]:
    return {"uri": ref.uri, "sha256": ref.sha256}
