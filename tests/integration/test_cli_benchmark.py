from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

from algocode.cli.main import app
from tests.support.git import init_git_repository


class CliBenchmarkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.project_root = init_git_repository(
            self.root / "project",
            {"main.py": "print('hello')\n"},
        )
        self.data_dir = self.root / "data"
        self.runner = CliRunner()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_baseline_benchmark_and_show(self) -> None:
        init = self.runner.invoke(
            app,
            ["init", "--path", str(self.project_root), "--data-dir", str(self.data_dir)],
        )
        self.assertEqual(init.exit_code, 0, init.output)
        task_result = self.runner.invoke(
            app,
            [
                "task",
                "create",
                "--objective",
                "Benchmark",
                "--project-root",
                str(self.project_root),
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )
        task_id = json.loads(task_result.stdout)["data"]["id"]
        baseline = self.runner.invoke(
            app,
            ["baseline", task_id, "--data-dir", str(self.data_dir)],
        )
        self.assertEqual(baseline.exit_code, 0, baseline.output)

        correctness_path = self.root / "correctness.yaml"
        correctness_path.write_text(
            """
mode: cases
comparison: line-trim
cases:
  - id: output
    expected_output: "hello"
""",
            encoding="utf-8",
        )
        correctness = self.runner.invoke(
            app,
            [
                "correctness",
                "run",
                task_id,
                "--spec",
                str(correctness_path),
                "--data-dir",
                str(self.data_dir),
            ],
        )
        self.assertEqual(correctness.exit_code, 0, correctness.output)

        benchmark_path = self.root / "benchmark.yaml"
        benchmark_path.write_text(
            """
warmup: 0
repeats: 1
""",
            encoding="utf-8",
        )
        benchmark = self.runner.invoke(
            app,
            [
                "benchmark",
                task_id,
                "--spec",
                str(benchmark_path),
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )
        self.assertEqual(benchmark.exit_code, 0, benchmark.output)
        payload = json.loads(benchmark.stdout)["data"]
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["summary"]["count"], 1)

        shown = self.runner.invoke(
            app,
            [
                "benchmark",
                task_id,
                "--show",
                payload["run_id"],
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )
        self.assertEqual(shown.exit_code, 0, shown.output)
        self.assertEqual(json.loads(shown.stdout)["data"]["target_kind"], "baseline")


if __name__ == "__main__":
    unittest.main()
