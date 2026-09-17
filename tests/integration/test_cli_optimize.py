from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from algocode.cli.commands.optimize import _candidate_correctness_state
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
            [
                "init",
                "--path",
                str(self.project_root),
                "--data-dir",
                str(self.data_dir),
                "--no-bootstrap",
            ],
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

    def test_optimize_without_task_id_reads_current_task_file(self) -> None:
        self.runner.invoke(
            app,
            [
                "init",
                "--path",
                str(self.project_root),
                "--data-dir",
                str(self.data_dir),
                "--no-bootstrap",
            ],
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
        state_dir = self.project_root / ".algocode"
        state_dir.mkdir(exist_ok=True)
        (state_dir / "current-task.json").write_text(
            json.dumps({"taskId": task_id, "dataDir": str(self.data_dir)}),
            encoding="utf-8",
        )

        previous = Path.cwd()
        try:
            os.chdir(self.project_root)
            result = self.runner.invoke(
                app,
                [
                    "optimize",
                    "--fake-provider",
                    "--stop-after",
                    "baseline",
                    "--json",
                ],
            )
        finally:
            os.chdir(previous)

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.stdout)["data"]
        self.assertEqual(payload["status"], "completed")

    def test_candidate_correctness_state_uses_matching_candidate_run(self) -> None:
        runs = [
            SimpleNamespace(
                id="corr_candidate",
                target_kind="candidate",
                target_id="cand_1",
                status=SimpleNamespace(value="failed"),
            ),
            SimpleNamespace(
                id="corr_baseline",
                target_kind="baseline",
                target_id="base_1",
                status=SimpleNamespace(value="passed"),
            ),
        ]

        state = _candidate_correctness_state("cand_1", runs)

        self.assertEqual(
            state,
            {
                "specPath": ".algocode/oracle/correctness.yaml",
                "resultId": "corr_candidate",
                "status": "failed",
            },
        )


if __name__ == "__main__":
    unittest.main()
