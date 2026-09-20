from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from algocode.domain.events import EventType
from algocode.domain.model import CandidateStatus, DecisionOutcome, TaskPhase
from algocode.runtime.agent import (
    AgentRuntime,
    _refinement_worthy,
    _resume_block_reason,
)


class RefinementWorthyTests(unittest.TestCase):
    def test_a_significant_gain_is_worth_refining(self) -> None:
        comparison = {
            "valid": True,
            "improvement_percent": 1.5,
            "statistically_significant": True,
        }

        self.assertTrue(_refinement_worthy(comparison))

    def test_an_invalid_comparison_is_never_worth_refining(self) -> None:
        comparison = {
            "valid": False,
            "improvement_percent": 48.47,
            "statistically_significant": True,
        }

        self.assertFalse(_refinement_worthy(comparison))

    def test_a_gain_that_is_not_significant_is_not(self) -> None:
        comparison = {
            "valid": True,
            "improvement_percent": 1.5,
            "statistically_significant": False,
        }

        self.assertFalse(_refinement_worthy(comparison))

    def test_a_regression_is_not_worth_refining(self) -> None:
        comparison = {
            "valid": True,
            "improvement_percent": -4.0,
            "statistically_significant": True,
        }

        self.assertFalse(_refinement_worthy(comparison))

    def test_a_flatter_growth_curve_is_worth_refining(self) -> None:
        self.assertTrue(_refinement_worthy({"valid": True, "growth_delta": 0.8}))

    def test_a_steeper_growth_curve_is_not(self) -> None:
        self.assertFalse(_refinement_worthy({"valid": True, "growth_delta": -0.8}))

    def test_missing_evidence_is_not_worth_refining(self) -> None:
        self.assertFalse(_refinement_worthy({}))
        self.assertFalse(_refinement_worthy({"valid": True, "improvement_percent": None}))

    def test_a_boolean_growth_delta_is_ignored(self) -> None:
        self.assertFalse(_refinement_worthy({"valid": True, "growth_delta": True}))


class ResumeBlockTests(unittest.TestCase):
    def test_a_decided_candidate_cannot_resume_implement(self) -> None:
        candidate = SimpleNamespace(id="candidate-1", status=CandidateStatus.INCONCLUSIVE)

        reason = _resume_block_reason(TaskPhase.IMPLEMENT, candidate)

        self.assertIsNotNone(reason)
        self.assertIn("inconclusive", reason or "")

    def test_an_editable_candidate_can_resume_implement(self) -> None:
        candidate = SimpleNamespace(id="candidate-1", status=CandidateStatus.EDITING)

        self.assertIsNone(_resume_block_reason(TaskPhase.IMPLEMENT, candidate))


class PhaseReenteredEventTests(unittest.IsolatedAsyncioTestCase):
    async def test_records_an_explainable_phase_back_jump(self) -> None:
        runtime = AgentRuntime.__new__(AgentRuntime)
        runtime._event_store = SimpleNamespace(
            read=AsyncMock(return_value=()),
            append=AsyncMock(),
        )

        await runtime._append_phase_reentered(
            task_id="task-1",
            from_phase=TaskPhase.COMPARE,
            to_phase=TaskPhase.IMPLEMENT,
            reason="valid positive evidence",
            candidate_id="candidate-1",
            iteration=1,
        )

        event = runtime._event_store.append.await_args.args[2][0]
        self.assertEqual(event.type, EventType.AGENT_PHASE_REENTERED)
        self.assertEqual(event.payload["from_phase"], "compare")
        self.assertEqual(event.payload["to_phase"], "implement")
        self.assertEqual(event.payload["candidate_id"], "candidate-1")


class RefinementGuardTests(unittest.IsolatedAsyncioTestCase):
    def _runtime(self, comparison, *, outcome: DecisionOutcome) -> AgentRuntime:
        runtime = AgentRuntime.__new__(AgentRuntime)
        runtime._decision_service = SimpleNamespace(
            get_for_candidate=AsyncMock(return_value=SimpleNamespace(outcome=outcome))
        )
        runtime._candidate_service = SimpleNamespace()
        runtime._benchmark_service = SimpleNamespace(
            list_for_task=AsyncMock(
                return_value=[
                    SimpleNamespace(target_kind="candidate", target_id="candidate-1")
                ]
            ),
            read_comparison=AsyncMock(return_value=comparison),
        )
        runtime._max_evals = 50
        runtime._model_evals_used = 0
        runtime._estimated_cost_usd = 0.0
        runtime._cost_budget_usd = None
        return runtime

    async def test_rejected_candidate_with_a_gain_is_refined(self) -> None:
        runtime = self._runtime(
            {
                "valid": True,
                "improvement_percent": 1.5,
                "statistically_significant": True,
            },
            outcome=DecisionOutcome.REJECTED,
        )

        self.assertTrue(await runtime._should_refine(SimpleNamespace(id="task-1"), "candidate-1"))

    async def test_inconclusive_candidate_is_not_refined(self) -> None:
        runtime = self._runtime(
            {
                "valid": True,
                "improvement_percent": 48.47,
                "statistically_significant": True,
            },
            outcome=DecisionOutcome.INCONCLUSIVE,
        )

        self.assertFalse(
            await runtime._should_refine(SimpleNamespace(id="task-1"), "candidate-1")
        )

    async def test_invalid_comparison_is_not_refined(self) -> None:
        runtime = self._runtime(
            {
                "valid": False,
                "improvement_percent": 48.47,
                "statistically_significant": True,
            },
            outcome=DecisionOutcome.REJECTED,
        )

        self.assertFalse(
            await runtime._should_refine(SimpleNamespace(id="task-1"), "candidate-1")
        )

    async def test_an_accepted_candidate_is_never_refined(self) -> None:
        runtime = self._runtime(
            {
                "valid": True,
                "improvement_percent": 9.0,
                "statistically_significant": True,
            },
            outcome=DecisionOutcome.ACCEPTED,
        )

        self.assertFalse(await runtime._should_refine(SimpleNamespace(id="task-1"), "candidate-1"))

    async def test_a_missing_comparison_is_not_refined(self) -> None:
        runtime = self._runtime(None, outcome=DecisionOutcome.REJECTED)

        self.assertFalse(await runtime._should_refine(SimpleNamespace(id="task-1"), "candidate-1"))

    async def test_exhausted_evaluation_budget_blocks_refinement(self) -> None:
        runtime = self._runtime(
            {
                "valid": True,
                "improvement_percent": 1.5,
                "statistically_significant": True,
            },
            outcome=DecisionOutcome.REJECTED,
        )
        runtime._model_evals_used = 50

        self.assertFalse(await runtime._should_refine(SimpleNamespace(id="task-1"), "candidate-1"))


if __name__ == "__main__":
    unittest.main()
