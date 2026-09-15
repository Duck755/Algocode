from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

from algocode.cli.main import app
from tests.support.git import init_git_repository


class CliProjectBaselineTests(unittest.TestCase):
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

    def test_init_task_and_baseline(self) -> None:
        init_result = self.runner.invoke(
            app,
            [
                "init",
                "--path",
                str(self.project_root),
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )
        self.assertEqual(init_result.exit_code, 0, init_result.output)
        project = json.loads(init_result.stdout)["data"]
        self.assertEqual(project["language"], "python")

        task_result = self.runner.invoke(
            app,
            [
                "task",
                "create",
                "--objective",
                "Optimize Python",
                "--project-root",
                str(self.project_root),
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )
        self.assertEqual(task_result.exit_code, 0, task_result.output)
        task = json.loads(task_result.stdout)["data"]
        self.assertEqual(task["project_id"], project["id"])

        baseline_result = self.runner.invoke(
            app,
            [
                "baseline",
                task["id"],
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )
        self.assertEqual(baseline_result.exit_code, 0, baseline_result.output)
        baseline = json.loads(baseline_result.stdout)["data"]
        self.assertEqual(baseline["task_id"], task["id"])
        self.assertEqual(baseline["revision"], project["git_revision"])

    def test_correctness_and_replay(self) -> None:
        init_result = self.runner.invoke(
            app,
            ["init", "--path", str(self.project_root), "--data-dir", str(self.data_dir), "--json"],
        )
        self.assertEqual(init_result.exit_code, 0, init_result.output)
        self.runner.invoke(
            app,
            [
                "task",
                "create",
                "--objective",
                "Correctness",
                "--project-root",
                str(self.project_root),
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )
        tasks = json.loads(
            self.runner.invoke(
                app, ["task", "list", "--data-dir", str(self.data_dir), "--json"]
            ).stdout
        )["data"]
        task_id = tasks[0]["id"]
        baseline = self.runner.invoke(app, ["baseline", task_id, "--data-dir", str(self.data_dir)])
        self.assertEqual(baseline.exit_code, 0, baseline.output)

        spec_path = self.root / "correctness.yaml"
        spec_path.write_text(
            """
mode: cases
comparison: line-trim
cases:
  - id: output
    expected_output: "hello\n"
""",
            encoding="utf-8",
        )
        result = self.runner.invoke(
            app,
            [
                "correctness",
                "run",
                task_id,
                "--spec",
                str(spec_path),
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.stdout)["data"]
        self.assertEqual(payload["status"], "passed")

        replay = self.runner.invoke(
            app,
            [
                "correctness",
                "replay",
                payload["result_id"],
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )
        self.assertEqual(replay.exit_code, 0, replay.output)
        self.assertNotEqual(
            json.loads(replay.stdout)["data"]["result_id"],
            payload["result_id"],
        )


if __name__ == "__main__":
    unittest.main()
