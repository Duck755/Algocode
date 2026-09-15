from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from algocode.bootstrap import build_context
from algocode.domain.errors import BaselineBuildFailed
from algocode.domain.events import EventType
from algocode.domain.model import TaskPhase, TaskStatus
from tests.support.git import init_git_repository


class BaselineServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.project_root = init_git_repository(
            self.root / "project",
            {"main.py": "def main():\n    return 42\n"},
        )
        self.context = build_context(data_dir=self.root / "data")
        self.project = await self.context.project_service.register(
            self.project_root,
            write_config=True,
        )
        self.task = await self.context.task_service.create_task(
            "Optimize the Python implementation",
            project_id=self.project.id,
        )

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_capture_baseline_persists_build_and_updates_task(self) -> None:
        baseline = await self.context.baseline_service.capture(self.task.id)

        self.assertEqual(baseline.task_id, self.task.id)
        self.assertEqual(baseline.revision.value, self.project.git_revision)
        self.assertIsNotNone(baseline.build_result_ref)
        restored = await self.context.baseline_service.get(baseline.id)
        self.assertEqual(restored, baseline)

        task = await self.context.task_service.get_task(self.task.id)
        self.assertEqual(task.baseline_id, baseline.id)
        self.assertEqual(task.status, TaskStatus.READY)
        self.assertEqual(task.current_phase, TaskPhase.ANALYZE)

        events = await self.context.event_store.read(str(self.task.id))
        self.assertEqual(
            [event.type for event in events],
            [
                EventType.TASK_CREATED,
                EventType.BASELINE_STARTED,
                EventType.BASELINE_CAPTURED,
            ],
        )
        output = await self.context.artifact_store.read_bytes(baseline.build_result_ref)
        self.assertIsInstance(output, bytes)

    async def test_failed_build_marks_task_failed(self) -> None:
        with self.assertRaises(BaselineBuildFailed):
            await self.context.baseline_service.capture(
                self.task.id,
                commands=((sys.executable, "-c", "raise SystemExit(3)"),),
            )

        task = await self.context.task_service.get_task(self.task.id)
        self.assertEqual(task.status, TaskStatus.FAILED)
        events = await self.context.event_store.read(str(self.task.id))
        self.assertEqual(events[-1].type, EventType.BASELINE_FAILED)


if __name__ == "__main__":
    unittest.main()
