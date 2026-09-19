"""Search archive inspired by OpenEvolve's Top+Diverse sampling.

The archive is intentionally small and evidence-based: it reads only candidates
that already passed correctness and have a persisted decision, then renders a
compact context for the next candidate generation step.
"""

from __future__ import annotations

from dataclasses import dataclass

from algocode.application.services.benchmark_service import BenchmarkService
from algocode.application.services.candidate_service import CandidateService
from algocode.application.services.correctness_service import CorrectnessService
from algocode.application.services.decision_service import DecisionService
from algocode.application.services.task_service import TaskService
from algocode.domain.model import BenchmarkStatus, CorrectnessStatus, DecisionOutcome


@dataclass(frozen=True, slots=True)
class SearchArchiveEntry:
    candidate_id: str
    parent_candidate_id: str | None
    outcome: DecisionOutcome
    improvement_percent: float
    patch_hash: str | None
    reason: str


class SearchArchiveService:
    """Build the population context used by multi-candidate search."""

    def __init__(
        self,
        task_service: TaskService,
        candidate_service: CandidateService,
        correctness_service: CorrectnessService,
        decision_service: DecisionService,
        benchmark_service: BenchmarkService,
    ) -> None:
        self._task_service = task_service
        self._candidate_service = candidate_service
        self._correctness_service = correctness_service
        self._decision_service = decision_service
        self._benchmark_service = benchmark_service

    async def entries(self, task_id: str) -> tuple[SearchArchiveEntry, ...]:
        task = await self._task_service.get_task(task_id)
        candidates = await self._candidate_service.list_for_task(task.id)
        correctness_runs = await self._correctness_service.list_for_task(task.id)
        passed_candidates = {
            run.target_id
            for run in correctness_runs
            if run.target_kind == "candidate" and run.status is CorrectnessStatus.PASSED
        }
        benchmark_runs = await self._benchmark_service.list_for_task(task.id)
        comparisons: dict[str, dict] = {}
        for run in benchmark_runs:
            if (
                run.target_kind != "candidate"
                or run.comparison_ref is None
                or run.status is not BenchmarkStatus.COMPLETED
            ):
                continue
            comparison = await self._benchmark_service.read_comparison(run)
            if comparison is not None:
                comparisons[run.target_id] = comparison

        result: list[SearchArchiveEntry] = []
        for candidate in candidates:
            candidate_id = str(candidate.id)
            if candidate_id not in passed_candidates:
                continue
            decision = await self._decision_service.get_for_candidate(candidate_id)
            if decision is None:
                continue
            comparison = comparisons.get(candidate_id)
            improvement = (
                float(comparison.get("improvement_percent", 0.0))
                if comparison is not None
                else 0.0
            )
            result.append(
                SearchArchiveEntry(
                    candidate_id=candidate_id,
                    parent_candidate_id=(
                        str(candidate.parent_candidate_id)
                        if candidate.parent_candidate_id is not None
                        else None
                    ),
                    outcome=decision.outcome,
                    improvement_percent=improvement,
                    patch_hash=candidate.patch_hash,
                    reason=decision.reason,
                )
            )
        return tuple(result)

    async def render_context(self, task_id: str, *, max_population: int) -> str:
        entries = await self.entries(task_id)
        if not entries:
            return ""
        selected = _select_top_and_diverse(entries, max_population=max_population)
        lines = ["[search archive]"]
        for entry in selected:
            parent = entry.parent_candidate_id or "root"
            lines.append(
                f"- candidate {entry.candidate_id} "
                f"(parent={parent}, outcome={entry.outcome.value}, "
                f"improvement={entry.improvement_percent:.4f}%): {entry.reason}"
            )
        return "\n".join(lines)


def _select_top_and_diverse(
    entries: tuple[SearchArchiveEntry, ...],
    *,
    max_population: int,
) -> tuple[SearchArchiveEntry, ...]:
    limit = max(1, max_population)
    selected: list[SearchArchiveEntry] = []
    selected_ids: set[str] = set()

    for entry in sorted(entries, key=lambda item: item.improvement_percent, reverse=True):
        if len(selected) >= limit:
            break
        if entry.candidate_id in selected_ids:
            continue
        selected.append(entry)
        selected_ids.add(entry.candidate_id)

    diverse = sorted(
        entries,
        key=lambda item: (item.patch_hash or item.candidate_id, item.candidate_id),
    )
    for entry in diverse:
        if len(selected) >= limit:
            break
        if entry.candidate_id in selected_ids:
            continue
        selected.append(entry)
        selected_ids.add(entry.candidate_id)

    return tuple(selected)
