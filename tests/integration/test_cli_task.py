from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

from algocode.cli.main import app


class CliTaskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temporary_directory.name)
        self.runner = CliRunner()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_create_list_and_show_task(self) -> None:
        create_result = self.runner.invoke(
            app,
            [
                "task",
                "create",
                "--objective",
                "优化矩阵乘法",
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )
        self.assertEqual(create_result.exit_code, 0, create_result.output)
        created = json.loads(create_result.stdout)["data"]
        self.assertEqual(created["objective"], "优化矩阵乘法")
        self.assertEqual(created["status"], "draft")

        list_result = self.runner.invoke(
            app,
            ["task", "list", "--data-dir", str(self.data_dir), "--json"],
        )
        self.assertEqual(list_result.exit_code, 0, list_result.output)
        tasks = json.loads(list_result.stdout)["data"]
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["id"], created["id"])

        show_result = self.runner.invoke(
            app,
            ["task", "show", created["id"], "--data-dir", str(self.data_dir), "--json"],
        )
        self.assertEqual(show_result.exit_code, 0, show_result.output)
        shown = json.loads(show_result.stdout)["data"]
        self.assertEqual(shown, created)

    def test_show_missing_task_returns_error(self) -> None:
        result = self.runner.invoke(
            app,
            ["task", "show", "task_missing", "--data-dir", str(self.data_dir)],
        )
        self.assertEqual(result.exit_code, 1)
        self.assertIn("was not found", result.output)


if __name__ == "__main__":
    unittest.main()
