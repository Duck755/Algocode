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
        if candidate.frozen_at is None:
            candidate = await self._candidate_service.freeze(candidate.id)
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
            reason = comparison.get("reason") if comparison is not None else None
            raise DecisionError(str(reason or "candidate benchmark comparison is invalid"))
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

    async def auto_decide(
        self,
        task_id: TaskId | str,
        candidate_id: CandidateId | str,
    ) -> Decision:
        """Decide a candidate from evidence without raising for negative outcomes."""

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
        if correctness is None or correctness.status is not CorrectnessStatus.PASSED:
            return await self.record_outcome(
                task.id,
                candidate.id,
                DecisionOutcome.REJECTED,
                reason="candidate correctness must pass before acceptance",
            )
        if correctness.result_ref is None:
            return await self.record_outcome(
                task.id,
                candidate.id,
                DecisionOutcome.REJECTED,
                reason="candidate correctness has no result artifact",
            )

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
            return await self.record_outcome(
                task.id,
                candidate.id,
                DecisionOutcome.INCONCLUSIVE,
                reason="valid candidate benchmark evidence is required before decision",
            )

        benchmark_result = await self._benchmark_service.read_result(benchmark)
        comparison = await self._benchmark_service.read_comparison(benchmark)
        if comparison is None or comparison.get("valid") is not True:
            return await self.record_outcome(
                task.id,
                candidate.id,
                DecisionOutcome.INCONCLUSIVE,
                reason=(
                    str(comparison.get("reason"))
                    if comparison is not None and comparison.get("reason")
                    else "candidate benchmark comparison is invalid"
                ),
                evidence_refs=(
                    benchmark.result_ref,
                    benchmark.comparison_ref,
                ),
            )

        issues = self._acceptance_issues(benchmark_result, comparison)
        if issues:
            improvement = float(comparison.get("improvement_percent", 0.0))
            joined = "; ".join(issues)
            if improvement < 0:
                outcome = DecisionOutcome.REJECTED
            elif (
                comparison.get("statistically_significant") is False
                or "variation exceeds" in joined
                or "no statistical significance evidence" in joined
                or "confidence interval crosses zero" in joined
            ):
                outcome = DecisionOutcome.INCONCLUSIVE
            else:
                outcome = DecisionOutcome.REJECTED
            return await self.record_outcome(
                task.id,
                candidate.id,
                outcome,
                reason=joined,
                evidence_refs=(
                    correctness.result_ref,
                    benchmark.result_ref,
                    benchmark.comparison_ref,
                ),
            )

        reason = "correctness and benchmark evidence passed acceptance policy"
        return await self.record_outcome(
            task.id,
            candidate.id,
            DecisionOutcome.ACCEPTED,
            reason=reason,
            evidence_refs=(
                correctness.result_ref,
                benchmark.result_ref,
                benchmark.comparison_ref,
            ),
        )

    async def reject(
        self,
        task_id: TaskId | str,
        candidate_id: CandidateId | str,
        *,
        reason: str = "",
    ) -> Decision:
        return await self.record_outcome(
            task_id,
            candidate_id,
            DecisionOutcome.REJECTED,
            reason=reason,
        )

    async def inconclusive(
        self,
        task_id: TaskId | str,
        candidate_id: CandidateId | str,
        *,
        reason: str = "",
    ) -> Decision:
        return await self.record_outcome(
            task_id,
            candidate_id,
            DecisionOutcome.INCONCLUSIVE,
            reason=reason,
        )

    async def record_outcome(
        self,
        task_id: TaskId | str,
        candidate_id: CandidateId | str,
        outcome: DecisionOutcome,
        *,
        reason: str = "",
        evidence_refs: tuple[ArtifactRef, ...] = (),
    ) -> Decision:
        task = await self._task_service.get_task(task_id)
        candidate = await self._candidate_service.get(candidate_id)
        if candidate.task_id != task.id:
            raise DecisionError("candidate does not belong to the task")
        decision = Decision(
            id=new_decision_id(),
            task_id=task.id,
            candidate_id=candidate.id,
            outcome=outcome,
            reason=reason,
            evidence_refs=list(evidence_refs),
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
                        "evidence_refs": [
                            _artifact_payload(ref) for ref in decision.evidence_refs
                        ],
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
        issues = self._acceptance_issues(benchmark_result, comparison)
        if issues:
            raise DecisionError(issues[0])

    def _acceptance_issues(
        self,
        benchmark_result: dict[str, object],
        comparison: dict[str, object],
    ) -> list[str]:
        issues: list[str] = []
        improvement = float(comparison.get("improvement_percent", 0.0))
        algorithmic_gain = _algorithmic_gain(comparison, self._acceptance_policy)
        if (
            improvement < self._acceptance_policy.min_median_improvement_percent
            and not algorithmic_gain
        ):
            issues.append(
                f"candidate improvement is below the acceptance threshold: {improvement:.6f}%"
            )
        max_variation = self._acceptance_policy.max_variation_percent
        if max_variation is not None:
            for key in ("baseline_summary", "candidate_summary"):
                summary = benchmark_result.get(key)
                if isinstance(summary, dict):
                    variation = float(
                        summary.get(
                            "robust_variation_percent",
                            summary.get("variation_percent", 0.0),
                        )
                    )
                    if variation > max_variation:
                        issues.append(
                            f"{key} variation exceeds acceptance threshold: {variation:.6f}%"
                        )
        if self._acceptance_policy.require_statistically_significant:
            statistically_significant = comparison.get("statistically_significant")
            if statistically_significant is False:
                p_value = comparison.get("p_value")
                detail = f" p_value={p_value:.4f}" if isinstance(p_value, (int, float)) else ""
                issues.append(
                    f"candidate improvement is not statistically significant{detail}"
                )
            if statistically_significant is None and "p_value" in comparison:
                issues.append(
                    "candidate comparison has no statistical significance evidence"
                )
            if statistically_significant is True and not _confidence_interval_supports_gain(
                comparison
            ):
                issues.append(
                    "candidate improvement confidence interval crosses zero"
                )
        for metric, threshold in (
            ("peak_memory", self._acceptance_policy.max_peak_memory_regression_percent),
            ("compile_time", self._acceptance_policy.max_compile_time_regression_percent),
        ):
            if threshold is None:
                continue
            regression = _metric_regression_percent(benchmark_result, metric)
            if regression is not None and regression > threshold:
                issues.append(
                    f"{metric} regression exceeds acceptance threshold: {regression:.6f}%"
                )
        return issues

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


def _algorithmic_gain(
    comparison: dict[str, object],
    policy: AcceptancePolicyConfig,
) -> bool:
    """True when the fitted growth exponent dropped enough to count.

    A rewrite that is slower on the smallest input but visibly flatter across
    sizes is exactly the case this exists for.
    """

    required_points = policy.growth_points_required
    required_drop = policy.min_growth_exponent_reduction
    if required_points <= 0 or required_drop <= 0:
        return False
    delta = comparison.get("growth_delta")
    points = comparison.get("growth_points")
    if isinstance(delta, bool) or isinstance(points, bool):
        return False
    if not isinstance(delta, int | float) or not isinstance(points, int | float):
        return False
    return int(points) >= required_points and float(delta) >= required_drop


def _confidence_interval_supports_gain(comparison: dict[str, object]) -> bool:
    """Return True when the paired improvement CI excludes zero.

    Missing CI evidence is treated as unavailable rather than invalid so older
    cached comparisons remain readable.
    """

    lower = comparison.get("ci_lower")
    upper = comparison.get("ci_upper")
    if isinstance(lower, bool) or isinstance(upper, bool):
        return True
    if not isinstance(lower, int | float) or not isinstance(upper, int | float):
        return True
    if comparison.get("pairing") != "paired":
        return True
    return float(lower) > 0.0 and float(upper) > 0.0


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
