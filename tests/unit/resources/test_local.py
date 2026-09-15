"""Local resource provider tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.benchmark.spec import BenchmarkSpec
from algocode.bootstrap import build_context
from algocode.correctness.spec import CorrectnessCase, CorrectnessSpec
from algocode.domain.model import TaskPhase
from algocode.tools import build_default_registry
from algocode.tools.types import ToolContext
from tests.support.git import init_git_repository


class LocalResourceProviderTests(unittest.IsolatedAsyncioTestCase):
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
            "Inspect resources",
            project_id=self.project.id,
        )
        self.baseline = await self.context.baseline_service.capture(self.task.id)
        await self.context.correctness_service.run_baseline(
            self.task.id,
            CorrectnessSpec(
                mode="cases",
                comparison="line-trim",
                cases=(CorrectnessCase(id="output", expected_output="hello"),),
            ),
        )

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_resolve_repo_baseline_candidate_and_artifact(self) -> None:
        repo = await self.context.resource_provider.resolve(
            "repo://main.py",
            workspace=self.project_root,
        )
        baseline = await self.context.resource_provider.resolve(
            f"resource://task/{self.task.id}/baseline"
        )
        candidate = await self.context.candidate_service.create(self.task.id)
        candidate_resource = await self.context.resource_provider.resolve(
            f"resource://task/{self.task.id}/candidate/{candidate.id}"
        )
        ref = await self.context.artifact_store.put(
            b"artifact-content",
            kind="test",
            mime_type="text/plain",
            metadata={"task_id": str(self.task.id)},
        )
        artifact = await self.context.resource_provider.resolve(ref.uri, mode="content")

        self.assertEqual(repo.trust, "untrusted")
        self.assertIsNone(repo.content)
        self.assertEqual(baseline.metadata["baseline_id"], self.baseline.id)
        self.assertEqual(candidate_resource.metadata["candidate_id"], str(candidate.id))
        self.assertEqual(artifact.content, "artifact-content")

    async def test_read_resource_tool(self) -> None:
        result = await build_default_registry().execute(
            "read_resource",
            {"uri": "repo://main.py", "mode": "content"},
            ToolContext(
                task=self.task,
                phase=TaskPhase.ANALYZE,
                workspace=self.project_root,
                resource_provider=self.context.resource_provider,
            ),
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(result.structured["trust"], "untrusted")
        self.assertIn("print('hello')", result.structured["content"])

    async def test_resolve_experiment_benchmark(self) -> None:
        baseline_run, _ = await self.context.benchmark_service.run_baseline(
            self.task.id,
            BenchmarkSpec(warmup=0, repeats=1),
        )

        resource = await self.context.resource_provider.resolve(
            f"resource://experiment/{baseline_run.id}/benchmark",
            mode="content",
        )

        self.assertEqual(resource.metadata["experiment_id"], baseline_run.id)
        self.assertIn('"target_kind": "baseline"', resource.content or "")


if __name__ == "__main__":
    unittest.main()
