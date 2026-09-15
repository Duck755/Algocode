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


class CliExperimentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.project_root = init_git_repository(
            self.root / "project",
            {"main.py": "print('hello')\n"},
        )
        self.data_dir = self.root / "data"
        self.context = build_context(data_dir=self.data_dir)
        self.project = await self.context.project_service.register(
            self.project_root,
            write_config=True,
        )
        self.task = await self.context.task_service.create_task(
            "Inspect experiment",
            project_id=self.project.id,
        )
        await self.context.baseline_service.capture(self.task.id)
        await self.context.correctness_service.run_baseline(
            self.task.id,
            CorrectnessSpec(
                mode="cases",
                comparison="line-trim",
                cases=(CorrectnessCase(id="output", expected_output="hello"),),
            ),
        )
        self.run, _ = await self.context.benchmark_service.run_baseline(
            self.task.id,
            BenchmarkSpec(warmup=0, repeats=1),
        )
        self.runner = CliRunner()

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_list_and_show_experiments_with_uniform_flags(self) -> None:
        listed = self.runner.invoke(
            app,
            [
                "experiment",
                "list",
                str(self.task.id),
                "--data-dir",
                str(self.data_dir),
                "--json",
                "--no-color",
                "--quiet",
                "--verbose",
            ],
        )
        self.assertEqual(listed.exit_code, 0, listed.output)
        listed_payload = json.loads(listed.stdout)
        self.assertTrue(listed_payload["ok"])
        self.assertEqual(listed_payload["command"], "experiment.list")
        self.assertEqual(listed_payload["data"][0]["experiment_id"], self.run.id)

        shown = self.runner.invoke(
            app,
            [
                "experiment",
                "show",
                self.run.id,
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )
        self.assertEqual(shown.exit_code, 0, shown.output)
        shown_payload = json.loads(shown.stdout)
        self.assertEqual(shown_payload["experiment_id"], self.run.id)
        self.assertEqual(shown_payload["data"]["experiment"]["experiment_id"], self.run.id)


if __name__ == "__main__":
    unittest.main()
