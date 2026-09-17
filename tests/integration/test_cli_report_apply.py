from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

from algocode.benchmark.spec import BenchmarkSpec
from algocode.bootstrap import build_context
from algocode.cli.main import app
from algocode.correctness.spec import CorrectnessCase, CorrectnessSpec
from tests.support.git import init_git_repository


class CliReportApplyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.project_root = init_git_repository(
            self.root / "project",
            {"main.py": "import time\ntime.sleep(0.02)\nprint('hello')\n"},
        )
        self.data_dir = self.root / "data"
        (self.project_root / ".algocode.yaml").write_text(
            "acceptancePolicy:\n  minMedianImprovementPercent: -1000\n",
            encoding="utf-8",
        )
        self.context = build_context(project_root=self.project_root, data_dir=self.data_dir)
        self.project = await self.context.project_service.register(
            self.project_root,
            write_config=True,
        )
        self.task = await self.context.task_service.create_task(
            "CLI report apply",
            project_id=self.project.id,
        )
        await self.context.baseline_service.capture(self.task.id)
        await self.context.correctness_service.run_baseline(
            self.task.id,
            CorrectnessSpec(
                mode="cases",
                comparison="line-trim",
                cases=(CorrectnessCase(id="baseline", expected_output="hello"),),
            ),
        )
        candidate = await self.context.candidate_service.create(self.task.id)
        (Path(candidate.workspace_ref) / "main.py").write_text(
            "print('hi')\n",
            encoding="utf-8",
        )
        candidate = await self.context.candidate_service.freeze(candidate.id)
        correctness_run, result = await self.context.correctness_service.run_target(
            self.task.id,
            CorrectnessSpec(
                mode="cases",
                comparison="line-trim",
                cases=(CorrectnessCase(id="candidate", expected_output="hi"),),
            ),
            target_kind="candidate",
            target_id=str(candidate.id),
            workspace_ref=candidate.workspace_ref,
        )
        self.assertTrue(result.passed)
        await self.context.benchmark_service.run_candidate(
            self.task.id,
            str(candidate.id),
            candidate.workspace_ref,
            correctness_run.id,
            BenchmarkSpec(warmup=0, repeats=1),
        )
        self.candidate = candidate
        self.runner = CliRunner()

    def test_current_project_short_commands(self) -> None:
        state_dir = self.project_root / ".algocode"
        state_dir.mkdir(exist_ok=True)
        (self.project_root / ".git" / "info" / "exclude").write_text(
            ".algocode/config.local.yaml\n.algocode/current-task.json\n.algocode/task.txt\n.algocode/cache/\n",
            encoding="utf-8",
        )
        (state_dir / "current-task.json").write_text(
            json.dumps(
                {
                    "taskId": str(self.task.id),
                    "candidateId": str(self.candidate.id),
                    "dataDir": str(self.data_dir),
                }
            ),
            encoding="utf-8",
        )

        previous = Path.cwd()
        try:
            os.chdir(self.project_root)
            status = self.runner.invoke(app, ["status", "--json"])
            review = self.runner.invoke(app, ["review", "--json"])
            diff = self.runner.invoke(app, ["diff", "--json"])
            applied = self.runner.invoke(app, ["apply", "--json"])
            rolled_back = self.runner.invoke(app, ["rollback", "--json"])
        finally:
            os.chdir(previous)

        self.assertEqual(status.exit_code, 0, status.output)
        self.assertEqual(review.exit_code, 0, review.output)
        self.assertEqual(diff.exit_code, 0, diff.output)
        self.assertEqual(applied.exit_code, 0, applied.output)
        self.assertEqual(rolled_back.exit_code, 0, rolled_back.output)
        self.assertEqual(json.loads(status.stdout)["data"]["taskId"], str(self.task.id))
        self.assertEqual(
            json.loads(review.stdout)["data"]["candidate"]["id"], str(self.candidate.id)
        )
        self.assertTrue(json.loads(diff.stdout)["data"]["patch"])
        self.assertTrue(json.loads(applied.stdout)["data"]["applied"])
        self.assertTrue(json.loads(rolled_back.stdout)["data"]["rolled_back"])

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_accept_report_apply_rollback_commands(self) -> None:
        accepted = self.runner.invoke(
            app,
            [
                "accept",
                str(self.task.id),
                str(self.candidate.id),
                "--reason",
                "cli test",
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )
        self.assertEqual(accepted.exit_code, 0, accepted.output)
        self.assertEqual(json.loads(accepted.stdout)["data"]["outcome"], "accepted")

        report = self.runner.invoke(
            app,
            ["report", str(self.task.id), "--json", "--data-dir", str(self.data_dir)],
        )
        self.assertEqual(report.exit_code, 0, report.output)
        self.assertEqual(json.loads(report.stdout)["data"]["taskId"], str(self.task.id))

        applied = self.runner.invoke(
            app,
            [
                "apply",
                str(self.task.id),
                str(self.candidate.id),
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )
        self.assertEqual(applied.exit_code, 0, applied.output)
        self.assertTrue(json.loads(applied.stdout)["data"]["applied"])

        rolled_back = self.runner.invoke(
            app,
            [
                "rollback",
                str(self.task.id),
                str(self.candidate.id),
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )
        self.assertEqual(rolled_back.exit_code, 0, rolled_back.output)
        self.assertTrue(json.loads(rolled_back.stdout)["data"]["rolled_back"])

    def test_retry_child_candidate_applies_to_task_baseline(self) -> None:
        parent_candidate = self.candidate

        async def scenario() -> None:
            baseline = await self.context.baseline_service.get_for_task(self.task.id)
            self.assertIsNotNone(baseline)
            child = await self.context.candidate_service.create(
                self.task.id,
                source_workspace=parent_candidate.workspace_ref,
                parent_candidate_id=str(parent_candidate.id),
            )
            self.assertEqual(child.parent_candidate_id, parent_candidate.id)
            self.assertEqual(child.fork_snapshot_hash, child.base_snapshot_hash)
            self.assertEqual(child.apply_base_snapshot_hash, baseline.snapshot_hash)
            self.assertNotEqual(child.base_snapshot_hash, baseline.snapshot_hash)
            (Path(child.workspace_ref) / "main.py").write_text(
                "print('child')\n",
                encoding="utf-8",
            )
            correctness_run, correctness = await self.context.correctness_service.run_target(
                self.task.id,
                CorrectnessSpec(
                    mode="cases",
                    comparison="line-trim",
                    cases=(CorrectnessCase(id="child", expected_output="child"),),
                ),
                target_kind="candidate",
                target_id=str(child.id),
                workspace_ref=child.workspace_ref,
            )
            self.assertTrue(correctness.passed)
            await self.context.benchmark_service.run_candidate(
                self.task.id,
                str(child.id),
                child.workspace_ref,
                correctness_run.id,
                BenchmarkSpec(warmup=0, repeats=1),
            )
            await self.context.decision_service.accept(self.task.id, child.id)
            result = await self.context.apply_service.apply(self.task.id, child.id)
            self.assertTrue(result["applied"])
            self.assertIn(
                "child",
                (self.project_root / "main.py").read_text(encoding="utf-8"),
            )
            await self.context.apply_service.rollback(self.task.id, child.id)
            self.assertIn(
                "hello",
                (self.project_root / "main.py").read_text(encoding="utf-8"),
            )

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
