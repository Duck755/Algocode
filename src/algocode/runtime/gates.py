"""Phase prerequisite gates."""

from __future__ import annotations

from dataclasses import dataclass

from algocode.domain.model import BenchmarkStatus, Candidate, CorrectnessStatus, Task, TaskPhase


@dataclass(frozen=True, slots=True)
class GateDecision:
    allowed: bool
    reason: str


class PhaseGate:
    def evaluate(
        self,
        *,
        task: Task,
        phase: TaskPhase,
        has_baseline: bool,
        candidates: list[Candidate],
        active_candidate_id: str | None = None,
        correctness_runs,
        benchmark_runs,
    ) -> GateDecision:
        if phase in {TaskPhase.CREATE, TaskPhase.ANALYZE, TaskPhase.BASELINE}:
            return GateDecision(True, "initial phase")
        if phase in {TaskPhase.PLAN, TaskPhase.GENERATE_CANDIDATE} and not has_baseline:
            return GateDecision(False, "baseline is required before planning")
        active_id = _active_candidate_id(candidates, active_candidate_id)
        if phase in {
            TaskPhase.IMPLEMENT,
            TaskPhase.VERIFY,
            TaskPhase.BENCHMARK,
            TaskPhase.COMPARE,
            TaskPhase.DECIDE,
        } and (
            active_id is None or not any(str(candidate.id) == active_id for candidate in candidates)
        ):
            return GateDecision(False, "candidate is required for this phase")
        if phase in {TaskPhase.BENCHMARK, TaskPhase.COMPARE, TaskPhase.DECIDE}:
            passed = any(
                run.target_kind == "candidate"
                and run.target_id == active_id
                and run.status is CorrectnessStatus.PASSED
                for run in correctness_runs
            )
            if not passed:
                return GateDecision(False, "candidate correctness must pass before benchmark")
        if phase in {TaskPhase.COMPARE, TaskPhase.DECIDE} and not any(
            run.target_kind == "candidate"
            and run.target_id == active_id
            and run.status is BenchmarkStatus.COMPLETED
            and run.comparison_ref is not None
            for run in benchmark_runs
        ):
            return GateDecision(False, "candidate benchmark evidence is required before comparison")
        return GateDecision(True, "phase prerequisites satisfied")


def _active_candidate_id(
    candidates: list[Candidate],
    requested: str | None,
) -> str | None:
    if requested is not None:
        return requested
    return str(candidates[0].id) if len(candidates) == 1 else None
