from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

from algocode.cli.main import app
from tests.support.git import init_git_repository


class CliTaskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.data_dir = self.root / "data"
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

    def test_show_task_uses_current_project_data_dir(self) -> None:
        create_result = self.runner.invoke(
            app,
            [
                "task",
                "create",
                "--objective",
                "Optimize with project state",
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )
        task_id = json.loads(create_result.stdout)["data"]["id"]
        state_dir = self.root / ".algocode"
        state_dir.mkdir()
        (state_dir / "current-task.json").write_text(
            json.dumps({"taskId": task_id, "dataDir": str(self.data_dir)}),
            encoding="utf-8",
        )

        previous = Path.cwd()
        try:
            os.chdir(self.root)
            show_result = self.runner.invoke(
                app,
                ["task", "show", task_id, "--json"],
            )
        finally:
            os.chdir(previous)

        self.assertEqual(show_result.exit_code, 0, show_result.output)
        self.assertEqual(json.loads(show_result.stdout)["data"]["id"], task_id)

    def test_default_task_storage_lives_in_project_cache(self) -> None:
        project_root = init_git_repository(
            self.root / "project",
            {"main.py": "print('hello')\n"},
        )
        init_result = self.runner.invoke(
            app,
            ["init", "--path", str(project_root), "--no-bootstrap"],
        )
        self.assertEqual(init_result.exit_code, 0, init_result.output)

        create_result = self.runner.invoke(
            app,
            [
                "task",
                "create",
                "--objective",
                "Use project-local storage",
                "--project-root",
                str(project_root),
                "--json",
            ],
        )
        self.assertEqual(create_result.exit_code, 0, create_result.output)
        task_id = json.loads(create_result.stdout)["data"]["id"]
        self.assertTrue((project_root / ".algocode" / "cache" / "algocode.db").is_file())

        previous = Path.cwd()
        try:
            os.chdir(project_root)
            show_result = self.runner.invoke(app, ["task", "show", task_id, "--json"])
        finally:
            os.chdir(previous)

        self.assertEqual(show_result.exit_code, 0, show_result.output)
        self.assertEqual(json.loads(show_result.stdout)["data"]["id"], task_id)


if __name__ == "__main__":
    unittest.main()
