from __future__ import annotations

import unittest

from algocode.domain.model import (
    CandidateStatus,
    ExperimentStatus,
    GitRevision,
    Task,
    TaskPhase,
    TaskStatus,
    new_project_id,
    new_task_id,
)


class ModelTests(unittest.TestCase):
    def test_new_task_has_expected_defaults(self) -> None:
        task = Task(id=new_task_id(), project_id=new_project_id(), objective="Optimize")
        self.assertEqual(task.status, TaskStatus.DRAFT)
        self.assertEqual(task.current_phase, TaskPhase.CREATE)
        self.assertIsNone(task.baseline_id)
        self.assertIsNone(task.active_candidate_id)

    def test_empty_git_revision_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            GitRevision("   ")

    def test_status_enums_have_stable_values(self) -> None:
        self.assertEqual(CandidateStatus.FROZEN.value, "frozen")
        self.assertEqual(ExperimentStatus.INVALID.value, "invalid")


if __name__ == "__main__":
    unittest.main()
