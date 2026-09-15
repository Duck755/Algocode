from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from algocode.bootstrap import build_context
from algocode.correctness.spec import CorrectnessCase, CorrectnessSpec
from algocode.domain.model import TaskPhase
from algocode.tools import build_default_registry
from algocode.tools.types import ToolContext
from algocode.workspace import GitRepository, GitWorkspaceManager
from tests.support.git import init_git_repository


class ToolActionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.project_root = init_git_repository(
            self.root / "project",
            {"main.py": "print('hello')\n"},
        )
        self.context = build_context(data_dir=self.root / "data")
        self.project = await self.context.project_service.register(
            self.project_root,
            write_config=True,
        )
        self.task = await self.context.task_service.create_task(
            "Optimize output",
            project_id=self.project.id,
        )
        self.baseline = await self.context.baseline_service.capture(self.task.id)
        await self.context.correctness_service.run_baseline(
            self.task.id,
            CorrectnessSpec(
                mode="cases",
                comparison="line-trim",
                cases=(CorrectnessCase(id="baseline", expected_output="hello"),),
            ),
        )

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_build_patch_correctness_and_benchmark_tools(self) -> None:
        registry = build_default_registry()
        baseline_context = ToolContext(
            task=self.task,
            phase=TaskPhase.VERIFY,
            workspace=Path(self.baseline.workspace_ref),
            artifact_store=self.context.artifact_store,
            language_registry=self.context.language_registry,
            correctness_service=self.context.correctness_service,
            benchmark_service=self.context.benchmark_service,
        )
        build_result = await registry.execute("build", {}, baseline_context)
        self.assertEqual(build_result.status, "success")

        repository = await GitRepository.discover(self.project_root)
        manager = GitWorkspaceManager(repository, self.root / "data")
        candidate = await manager.create_candidate(
            str(self.task.id),
            self.project.git_revision,
        )
        patch = (
            "diff --git a/main.py b/main.py\n"
            "--- a/main.py\n"
            "+++ b/main.py\n"
            "@@ -1 +1 @@\n"
            "-print('hello')\n"
            "+print('hi')\n"
        )
        candidate_context = ToolContext(
            task=self.task,
            phase=TaskPhase.IMPLEMENT,
            workspace=candidate.path,
            candidate_id="cand_1",
            artifact_store=self.context.artifact_store,
            language_registry=self.context.language_registry,
            correctness_service=self.context.correctness_service,
            benchmark_service=self.context.benchmark_service,
            protected_files=("tests/", ".algocode.yaml"),
        )
        applied = await registry.execute(
            "apply_patch",
            {"patch": patch},
            candidate_context,
        )
        self.assertEqual(applied.status, "success", applied.summary)

        correctness = await registry.execute(
            "run_correctness",
            {
                "spec": {
                    "mode": "cases",
                    "comparison": "line-trim",
                    "cases": [{"id": "candidate", "expected_output": "hi"}],
                }
            },
            replace(candidate_context, phase=TaskPhase.VERIFY),
        )
        self.assertEqual(correctness.status, "success", correctness.summary)

        benchmark_context = ToolContext(
            task=self.task,
            phase=TaskPhase.BENCHMARK,
            workspace=candidate.path,
            candidate_id="cand_1",
            correctness_result_id=str(correctness.structured["result_id"]),
            artifact_store=self.context.artifact_store,
            language_registry=self.context.language_registry,
            correctness_service=self.context.correctness_service,
            benchmark_service=self.context.benchmark_service,
        )
        benchmark = await registry.execute(
            "run_benchmark",
            {"spec": {"warmup": 0, "repeats": 1}},
            benchmark_context,
        )

        self.assertEqual(benchmark.status, "success", benchmark.summary)
        self.assertTrue(benchmark.structured["comparison_valid"])


if __name__ == "__main__":
    unittest.main()
