from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from algocode.domain.model import DecisionOutcome
from algocode.runtime.agent import AgentRuntime


class SearchGuardTests(unittest.IsolatedAsyncioTestCase):
    def _runtime(self, decision_outcome: DecisionOutcome) -> AgentRuntime:
        runtime = AgentRuntime.__new__(AgentRuntime)
        runtime._candidate_service = object()
        runtime._decision_service = SimpleNamespace(
            get_for_candidate=AsyncMock(
                return_value=SimpleNamespace(outcome=decision_outcome)
            )
        )
        runtime._max_candidates = 2
        runtime._max_iterations = 2
        runtime._max_evals = 50
        runtime._model_evals_used = 0
        runtime._estimated_cost_usd = 0.0
        runtime._cost_budget_usd = None
        return runtime

    async def test_continues_for_rejected_candidate(self) -> None:
        runtime = self._runtime(DecisionOutcome.REJECTED)
        self.assertTrue(
            await runtime._should_continue_search(
                task=object(),
                candidates=[object()],
                candidate_id="candidate-1",
                candidate_iterations=0,
            )
        )

    async def test_stops_for_accepted_candidate(self) -> None:
        runtime = self._runtime(DecisionOutcome.ACCEPTED)
        self.assertFalse(
            await runtime._should_continue_search(
                task=object(),
                candidates=[object()],
                candidate_id="candidate-1",
                candidate_iterations=0,
            )
        )

    async def test_stops_at_candidate_limit(self) -> None:
        runtime = self._runtime(DecisionOutcome.REJECTED)
        self.assertFalse(
            await runtime._should_continue_search(
                task=object(),
                candidates=[object(), object()],
                candidate_id="candidate-1",
                candidate_iterations=0,
            )
        )

    async def test_stops_at_cost_budget(self) -> None:
        runtime = self._runtime(DecisionOutcome.REJECTED)
        runtime._cost_budget_usd = 1.0
        runtime._estimated_cost_usd = 1.0
        self.assertFalse(
            await runtime._should_continue_search(
                task=object(),
                candidates=[object()],
                candidate_id="candidate-1",
                candidate_iterations=0,
            )
        )

    async def test_stops_at_eval_limit(self) -> None:
        runtime = self._runtime(DecisionOutcome.REJECTED)
        runtime._model_evals_used = 50
        self.assertFalse(
            await runtime._should_continue_search(
                task=object(),
                candidates=[object()],
                candidate_id="candidate-1",
                candidate_iterations=0,
            )
        )


if __name__ == "__main__":
    unittest.main()
