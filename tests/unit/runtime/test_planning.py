from __future__ import annotations

import json
import unittest

from algocode.runtime.planning import parse_optimization_plan


def _plan(**overrides: object) -> str:
    """A minimal but complete optimization plan, as JSON text."""

    payload: dict[str, object] = {
        "summary": "Replace the cubic all-pairs loop",
        "strategy": "Run Dijkstra once per source",
        "algorithm": "repeated Dijkstra",
        "complexityBefore": "O(n^3)",
        "complexityAfter": "O(n^2 log n)",
        "whyFaster": "reuses the shortest path tree instead of rebuilding it",
        "structureRef": "problemStructure.operationAlgebra",
        "steps": [
            {
                "id": "replace-algorithm",
                "description": "Implement repeated Dijkstra in test.py",
                "files": ["test.py"],
                "verification": ["Run the checker command"],
            }
        ],
    }
    payload.update(overrides)
    return json.dumps(payload)


class OptimizationPlanTests(unittest.TestCase):
    def test_plan_accepts_json_code_fence(self) -> None:
        plan = parse_optimization_plan(
            f"```json\n{_plan(protectedFiles=['oracle/check.py'])}\n```"
        )

        self.assertEqual(plan.strategy, "Run Dijkstra once per source")
        self.assertEqual(plan.steps[0].files, ("test.py",))
        self.assertEqual(plan.protected_files, ("oracle/check.py",))
        self.assertEqual(plan.algorithm, "repeated Dijkstra")
        self.assertEqual(plan.complexity_after, "O(n^2 log n)")

    def test_plan_accepts_action_alias_for_description(self) -> None:
        plan = parse_optimization_plan(
            _plan(steps=[{"id": "s1", "action": "Read the implementation."}])
        )

        self.assertEqual(plan.steps[0].description, "Read the implementation.")

    def test_plan_parses_retry_decision(self) -> None:
        plan = parse_optimization_plan(
            _plan(
                retryDecision={
                    "mode": "continue",
                    "basedOnAttempt": 4,
                    "parentAttempt": 4,
                    "directionId": "reduce-frames",
                    "directionState": "active",
                    "reason": "The direction is not exhausted.",
                    "preserveChanges": ["preserve inlined reply handling"],
                }
            )
        )

        self.assertIsNotNone(plan.retry_decision)
        self.assertEqual(plan.retry_decision.mode, "continue")
        self.assertEqual(plan.retry_decision.parent_attempt, 4)

    def test_plan_requires_algorithm_evidence(self) -> None:
        with self.assertRaises(ValueError) as caught:
            parse_optimization_plan(
                json.dumps(
                    {
                        "summary": "Replace something",
                        "strategy": "Patch it",
                        "steps": [{"id": "s1", "description": "Patch the loop."}],
                    }
                )
            )

        message = str(caught.exception)
        self.assertIn("algorithm", message)
        self.assertIn("complexityBefore", message)
        self.assertIn("whyFaster", message)


if __name__ == "__main__":
    unittest.main()
