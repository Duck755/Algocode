from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from algocode.application.services.project_state import (
    find_current_task,
    read_current_task,
    update_current_task,
)


class ProjectStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name).resolve()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _write_state(self, directory: Path, payload: dict[str, Any]) -> Path:
        state_dir = directory / ".algocode"
        state_dir.mkdir(parents=True, exist_ok=True)
        path = state_dir / "current-task.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def _read_state(self, directory: Path) -> dict[str, Any]:
        path = directory / ".algocode" / "current-task.json"
        return json.loads(path.read_text(encoding="utf-8"))


class UpdateCurrentTaskTests(ProjectStateTests):
    def test_does_not_inherit_a_parent_project_state(self) -> None:
        parent = self.root / "parent"
        child = parent / "child"
        child.mkdir(parents=True)
        self._write_state(parent, {"taskId": "task_stale", "dataDir": "stale-dir"})

        update_current_task(project_root=child, taskId="task_child", status="running")

        state = self._read_state(child)
        self.assertEqual(state["taskId"], "task_child")
        self.assertNotIn("stale", json.dumps(state))

    def test_parent_state_file_is_left_untouched(self) -> None:
        parent = self.root / "parent"
        child = parent / "child"
        child.mkdir(parents=True)
        path = self._write_state(parent, {"taskId": "task_stale"})
        before = path.read_text(encoding="utf-8")

        update_current_task(project_root=child, status="running")

        self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_keeps_the_same_directory_history(self) -> None:
        project = self.root / "project"
        project.mkdir()
        self._write_state(
            project,
            {"taskId": "task_1", "baselineId": "base_1", "status": "draft"},
        )

        update_current_task(project_root=project, status="completed")

        state = self._read_state(project)
        self.assertEqual(state["taskId"], "task_1")
        self.assertEqual(state["baselineId"], "base_1")
        self.assertEqual(state["status"], "completed")

    def test_writes_project_identity_defaults(self) -> None:
        project = self.root / "fresh"
        project.mkdir()

        update_current_task(project_root=project, taskId="task_9")

        state = self._read_state(project)
        self.assertEqual(state["schemaVersion"], 1)
        self.assertEqual(state["root"], str(project))
        self.assertEqual(state["contractPath"], ".algocode/contract.json")
        self.assertEqual(state["taskSummaryPath"], ".algocode/task.txt")
        self.assertIn("updatedAt", state)

    def test_always_rewrites_root_to_the_given_project(self) -> None:
        project = self.root / "project"
        project.mkdir()
        self._write_state(project, {"root": "C:/somewhere/else"})

        update_current_task(project_root=project, status="running")

        self.assertEqual(self._read_state(project)["root"], str(project))


class ReadCurrentTaskTests(ProjectStateTests):
    def test_find_current_task_still_walks_upwards(self) -> None:
        parent = self.root / "parent"
        child = parent / "child"
        child.mkdir(parents=True)
        self._write_state(parent, {"taskId": "task_parent"})

        found = find_current_task(child)

        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(found["taskId"], "task_parent")

    def test_read_current_task_never_walks_upwards(self) -> None:
        parent = self.root / "parent"
        child = parent / "child"
        child.mkdir(parents=True)
        self._write_state(parent, {"taskId": "task_parent"})

        self.assertIsNone(read_current_task(child))

    def test_read_current_task_returns_this_directory_state(self) -> None:
        project = self.root / "project"
        project.mkdir()
        self._write_state(project, {"taskId": "task_here"})

        state = read_current_task(project)

        self.assertIsNotNone(state)
        assert state is not None
        self.assertEqual(state["taskId"], "task_here")

    def test_corrupt_state_reads_as_missing(self) -> None:
        project = self.root / "project"
        state_dir = project / ".algocode"
        state_dir.mkdir(parents=True)
        (state_dir / "current-task.json").write_text("{not json", encoding="utf-8")

        self.assertIsNone(read_current_task(project))
        self.assertIsNone(find_current_task(project))


if __name__ == "__main__":
    unittest.main()