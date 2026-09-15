from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from algocode.bootstrap import build_context
from algocode.correctness.spec import CorrectnessCase, CorrectnessSpec
from algocode.domain.events import EventType
from algocode.domain.model import CorrectnessStatus, FailureKind, TaskStatus
from algocode.workspace import GitRepository, GitWorkspaceManager
from tests.support.git import init_git_repository


class CorrectnessServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.project_root = init_git_repository(
            self.root / "project",
            {"main.py": ("import sys\nsys.stdout.write(sys.stdin.read().upper())\n")},
        )
        self.context = build_context(data_dir=self.root / "data")
        self.project = await self.context.project_service.register(
            self.project_root,
            write_config=True,
        )
        self.task = await self.context.task_service.create_task(
            "Optimize uppercase conversion",
            project_id=self.project.id,
        )
        self.baseline = await self.context.baseline_service.capture(self.task.id)

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_correctness_pass_updates_baseline_and_can_replay(self) -> None:
        spec = CorrectnessSpec(
            mode="cases",
            cases=(CorrectnessCase(id="upper", input="hello", expected_output="HELLO"),),
        )

        run, result = await self.context.correctness_service.run_baseline(self.task.id, spec)

        self.assertTrue(result.passed)
        self.assertEqual(run.status, CorrectnessStatus.PASSED)
        self.assertEqual(run.failure_kind, None)
        baseline = await self.context.baseline_service.get(self.baseline.id)
        self.assertEqual(baseline.correctness_result_ref, run.result_ref)
        events = await self.context.event_store.read(str(self.task.id))
        self.assertEqual(
            [event.type for event in events[-2:]],
            [EventType.CORRECTNESS_STARTED, EventType.CORRECTNESS_PASSED],
        )

        replay, replay_result = await self.context.correctness_service.replay(run.id)
        self.assertTrue(replay_result.passed)
        self.assertNotEqual(replay.id, run.id)

    async def test_correctness_failure_is_persisted(self) -> None:
        spec = CorrectnessSpec(
            mode="cases",
            cases=(CorrectnessCase(id="wrong", input="hello", expected_output="WRONG"),),
        )

        run, result = await self.context.correctness_service.run_baseline(self.task.id, spec)

        self.assertFalse(result.passed)
        self.assertEqual(run.status, CorrectnessStatus.FAILED)
        self.assertIsNotNone(run.result_ref)
        events = await self.context.event_store.read(str(self.task.id))
        self.assertEqual(events[-1].type, EventType.CORRECTNESS_FAILED)
        task = await self.context.task_service.get_task(self.task.id)
        self.assertEqual(task.status, TaskStatus.FAILED)

    async def test_candidate_protected_file_change_is_failure(self) -> None:
        repository = await GitRepository.discover(self.project_root)
        manager = GitWorkspaceManager(repository, self.root / "data")
        candidate = await manager.create_candidate(
            str(self.task.id),
            self.project.git_revision,
        )
        spec = CorrectnessSpec(
            mode="cases",
            run_command=(sys.executable, str(candidate.path / "main.py")),
            cases=(CorrectnessCase(id="safe", expected_output=""),),
        )

        run, result = await self.context.correctness_service.run_target(
            self.task.id,
            spec,
            target_kind="candidate",
            target_id="cand_test",
            workspace_ref=candidate.path,
            changed_paths=("tests/test_main.py",),
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.failure_kind, FailureKind.PROTECTED_FILE_CHANGED)
        self.assertEqual(run.target_kind, "candidate")
        task = await self.context.task_service.get_task(self.task.id)
        self.assertEqual(task.status, TaskStatus.READY)


if __name__ == "__main__":
    unittest.main()
