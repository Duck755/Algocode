from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from algocode.application.services.search_archive_service import SearchArchiveService
from algocode.domain.model import BenchmarkStatus, CorrectnessStatus, DecisionOutcome


class SearchArchiveServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_renders_top_and_diverse_verified_candidates(self) -> None:
        task = SimpleNamespace(id="task-1")
        task_service = SimpleNamespace(get_task=AsyncMock(return_value=task))

        candidates = [
            SimpleNamespace(id="c1", parent_candidate_id=None, patch_hash="aaaa"),
            SimpleNamespace(id="c2", parent_candidate_id="c1", patch_hash="bbbb"),
            SimpleNamespace(id="c3", parent_candidate_id="c1", patch_hash="bbbb"),
        ]
        candidate_service = SimpleNamespace(list_for_task=AsyncMock(return_value=candidates))

        correctness_runs = [
            SimpleNamespace(
                target_kind="candidate", target_id="c1", status=CorrectnessStatus.PASSED
            ),
            SimpleNamespace(
                target_kind="candidate", target_id="c2", status=CorrectnessStatus.PASSED
            ),
            SimpleNamespace(
                target_kind="candidate", target_id="c3", status=CorrectnessStatus.FAILED
            ),
        ]
        correctness_service = SimpleNamespace(
            list_for_task=AsyncMock(return_value=correctness_runs)
        )

        decisions = {
            "c1": SimpleNamespace(outcome=DecisionOutcome.ACCEPTED, reason="good"),
            "c2": SimpleNamespace(outcome=DecisionOutcome.REJECTED, reason="slower"),
        }
        decision_service = SimpleNamespace(
            get_for_candidate=AsyncMock(
                side_effect=lambda candidate_id: decisions.get(candidate_id)
            )
        )

        benchmark_runs = [
            SimpleNamespace(
                target_kind="candidate",
                target_id="c1",
                comparison_ref="ref",
                status=BenchmarkStatus.COMPLETED,
            ),
            SimpleNamespace(
                target_kind="candidate",
                target_id="c2",
                comparison_ref="ref",
                status=BenchmarkStatus.COMPLETED,
            ),
        ]
        benchmark_service = SimpleNamespace(
            list_for_task=AsyncMock(return_value=benchmark_runs),
            read_comparison=AsyncMock(
                side_effect=lambda run: (
                    {"improvement_percent": 8.5}
                    if run.target_id == "c1"
                    else {"improvement_percent": -2.0}
                )
            ),
        )

        service = SearchArchiveService(
            task_service=task_service,
            candidate_service=candidate_service,
            correctness_service=correctness_service,
            decision_service=decision_service,
            benchmark_service=benchmark_service,
        )
        context = await service.render_context("task-1", max_population=2)

        self.assertIn("[search archive]", context)
        self.assertIn("candidate c1", context)
        self.assertIn("candidate c2", context)
        self.assertNotIn("candidate c3", context)


if __name__ == "__main__":
    unittest.main()
