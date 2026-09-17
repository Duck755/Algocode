from __future__ import annotations

import unittest

from algocode.runtime.planning import parse_optimization_plan


class OptimizationPlanTests(unittest.TestCase):
    def test_plan_accepts_json_code_fence(self) -> None:
        plan = parse_optimization_plan(
            """```json
            {
              "summary": "Replace the cubic all-pairs loop",
              "strategy": "Run Dijkstra once per source",
              "steps": [
                {
                  "id": "replace-algorithm",
                  "description": "Implement repeated Dijkstra in test.py",
                  "files": ["test.py"],
                  "verification": ["Run the checker command"]
                }
              ],
              "protectedFiles": ["oracle/check.py"]
            }
            ```"""
        )

        self.assertEqual(plan.strategy, "Run Dijkstra once per source")
        self.assertEqual(plan.steps[0].files, ("test.py",))
        self.assertEqual(plan.protected_files, ("oracle/check.py",))

    def test_plan_accepts_action_alias_for_description(self) -> None:
        plan = parse_optimization_plan(
            """{
              "summary": "Optimize",
              "strategy": "Inspect then patch",
              "steps": [
                {"id": "s1", "action": "Read the implementation."}
              ]
            }"""
        )

        self.assertEqual(plan.steps[0].description, "Read the implementation.")

    def test_plan_parses_retry_decision(self) -> None:
        plan = parse_optimization_plan(
            """{
              "summary": "Continue the winning direction",
              "strategy": "Preserve the prior changes.",
              "steps": [{"id": "s1", "description": "Continue."}],
              "retryDecision": {
                "mode": "continue",
                "basedOnAttempt": 4,
                "parentAttempt": 4,
                "directionId": "reduce-frames",
                "directionState": "active",
                "reason": "The direction is not exhausted.",
                "preserveChanges": ["preserve inlined reply handling"]
              }
            }"""
        )

        self.assertIsNotNone(plan.retry_decision)
        self.assertEqual(plan.retry_decision.mode, "continue")
        self.assertEqual(plan.retry_decision.parent_attempt, 4)


if __name__ == "__main__":
    unittest.main()
