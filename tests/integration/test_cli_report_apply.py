from __future__ import annotations

import json
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


if __name__ == "__main__":
    unittest.main()
