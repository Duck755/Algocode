from __future__ import annotations

import unittest

from algocode.domain.model import (
    new_candidate_id,
    new_decision_id,
    new_experiment_id,
    new_project_id,
    new_task_id,
)


class IdTests(unittest.TestCase):
    def test_ids_have_stable_prefixes(self) -> None:
        self.assertTrue(new_task_id().startswith("task_"))
        self.assertTrue(new_candidate_id().startswith("cand_"))
        self.assertTrue(new_experiment_id().startswith("exp_"))
        self.assertTrue(new_decision_id().startswith("dec_"))
        self.assertTrue(new_project_id().startswith("prj_"))

    def test_ids_are_unique(self) -> None:
        values = {new_task_id() for _ in range(100)}
        self.assertEqual(len(values), 100)


if __name__ == "__main__":
    unittest.main()
