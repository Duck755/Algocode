from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

from algocode.cli.main import app
from tests.support.git import init_git_repository


class CliOptimizeTests(unittest.TestCase):
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

    def test_fake_provider_optimize(self) -> None:
        self.runner.invoke(
            app,
            ["init", "--path", str(self.project_root), "--data-dir", str(self.data_dir)],
        )
        task_result = self.runner.invoke(
            app,
            [
                "task",
                "create",
                "--objective",
                "Optimize",
                "--project-root",
                str(self.project_root),
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )
        task_id = json.loads(task_result.stdout)["data"]["id"]

        result = self.runner.invoke(
            app,
            [
                "optimize",
                task_id,
                "--fake-provider",
                "--stop-after",
                "baseline",
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.stdout)["data"]
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["completed_phases"][-1], "baseline")
        self.assertGreater(payload["tool_calls"], 0)


if __name__ == "__main__":
    unittest.main()
