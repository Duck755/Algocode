from __future__ import annotations

import statistics
import tempfile
import unittest
from pathlib import Path

from algocode.benchmark.spec import BenchmarkSpec
from algocode.bootstrap import build_context
from algocode.correctness.spec import CorrectnessCase, CorrectnessSpec
from algocode.domain.errors import BenchmarkError
from algocode.domain.events import EventType
from algocode.domain.model import BenchmarkStatus
from algocode.workspace import GitRepository, GitWorkspaceManager
from tests.support.git import init_git_repository


class BenchmarkServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.project_root = init_git_repository(
            self.root / "project",
            {"main.py": "import time\ntime.sleep(0.02)\n"},
        )
        self.context = build_context(data_dir=self.root / "data")
        self.project = await self.context.project_service.register(
            self.project_root,
            write_config=True,
        )
        self.task = await self.context.task_service.create_task(
            "Optimize sleep",
            project_id=self.project.id,
        )
        self.baseline = await self.context.baseline_service.capture(self.task.id)

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_baseline_benchmark_and_candidate_comparison(self) -> None:
        correctness_spec = CorrectnessSpec(
            mode="cases",
            cases=(CorrectnessCase(id="empty", expected_output=""),),
        )
        await self.context.correctness_service.run_baseline(self.task.id, correctness_spec)
        benchmark_spec = BenchmarkSpec(warmup=0, repeats=2)

        baseline_run, baseline_result = await self.context.benchmark_service.run_baseline(
            self.task.id,
            benchmark_spec,
        )
        self.assertEqual(baseline_run.status, BenchmarkStatus.COMPLETED)
        self.assertTrue(baseline_result.valid)
        baseline = await self.context.baseline_service.get(self.baseline.id)
        self.assertEqual(baseline.benchmark_result_ref, baseline_run.result_ref)

        repository = await GitRepository.discover(self.project_root)
        manager = GitWorkspaceManager(repository, self.root / "data")
        candidate = await manager.create_candidate(
            str(self.task.id),
            self.project.git_revision,
        )
        (candidate.path / "main.py").write_text(
            "import time\ntime.sleep(0.005)\n",
            encoding="utf-8",
        )
        _, candidate_correctness = await self.context.correctness_service.run_target(
            self.task.id,
            correctness_spec,
            target_kind="candidate",
            target_id="cand_1",
            workspace_ref=candidate.path,
        )
        self.assertTrue(candidate_correctness.passed)
        correctness_runs = await self.context.correctness_service.list_for_task(self.task.id)
        candidate_correctness_run = next(
            run for run in correctness_runs if run.target_kind == "candidate"
        )

        (
            candidate_run,
            candidate_result,
            comparison,
        ) = await self.context.benchmark_service.run_candidate(
            self.task.id,
            "cand_1",
            candidate.path,
            candidate_correctness_run.id,
            benchmark_spec,
        )

        self.assertEqual(candidate_run.status, BenchmarkStatus.COMPLETED)
        self.assertTrue(candidate_result.valid)
        self.assertTrue(comparison.valid)
        self.assertEqual(candidate_result.comparison_key, baseline_result.comparison_key)
        self.assertGreater(comparison.baseline_median, 0)
        artifact = await self.context.benchmark_service.read_result(candidate_run)
        baseline_values = [
            sample["value"]
            for sample in artifact["samples"]
            if sample["target_kind"] == "baseline" and sample["phase"] == "measured"
        ]
        candidate_values = [
            sample["value"]
            for sample in artifact["samples"]
            if sample["target_kind"] == "candidate" and sample["phase"] == "measured"
        ]
        self.assertEqual(artifact["baseline_summary"]["count"], len(baseline_values))
        self.assertEqual(artifact["candidate_summary"]["count"], len(candidate_values))
        self.assertAlmostEqual(
            artifact["baseline_summary"]["median"],
            statistics.median(baseline_values),
        )
        self.assertAlmostEqual(comparison.baseline_median, statistics.median(baseline_values))
        self.assertAlmostEqual(comparison.candidate_median, statistics.median(candidate_values))
        events = await self.context.event_store.read(str(self.task.id))
        self.assertIn(EventType.BENCHMARK_SAMPLES_CAPTURED, [event.type for event in events])
        self.assertIn(EventType.COMPARISON_PRODUCED, [event.type for event in events])

    async def test_baseline_benchmark_requires_correctness(self) -> None:
        with self.assertRaisesRegex(BenchmarkError, "correctness must pass"):
            await self.context.benchmark_service.run_baseline(
                self.task.id,
                BenchmarkSpec(warmup=0, repeats=1),
            )


if __name__ == "__main__":
    unittest.main()
