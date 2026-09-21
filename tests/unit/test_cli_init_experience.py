from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from algocode.application.services.contract_service import (
    ContractDiscoveryService,
    ProjectContract,
)
from algocode.cli.main import app
from tests.support.git import init_git_repository


class InitExperienceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.data_dir = self.root / "data"
        self.runner = CliRunner()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _project(self, files: dict[str, str]) -> Path:
        return init_git_repository(self.root / "project", files)

    def test_json_output_stays_pure_and_quiet(self) -> None:
        project_root = self._project({"main.py": "print('hello')\n"})
        result = self.runner.invoke(
            app,
            [
                "init",
                "--path",
                str(project_root),
                "--data-dir",
                str(self.data_dir),
                "--no-bootstrap",
                "--json",
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(result.stderr, "")

    def test_bootstrap_streams_stage_rail_and_evidence(self) -> None:
        project_root = self._project({"test.py": "print('value=42')\nprint('elapsed=0.500000')\n"})
        contract = ProjectContract(
            purpose="Deterministic entrypoint.",
            performance_goal="Reduce the test entrypoint runtime.",
        )
        with patch.object(
            ContractDiscoveryService,
            "discover",
            new=AsyncMock(return_value=contract),
        ):
            result = self.runner.invoke(
                app,
                [
                    "init",
                    "--path",
                    str(project_root),
                    "--data-dir",
                    str(self.data_dir),
                    "--progress",
                ],
            )
        self.assertEqual(result.exit_code, 0, result.output)
        for stage in ("SCAN", "CONTRACT", "BASELINE", "READY"):
            self.assertIn(stage, result.stderr)
        self.assertIn("Evidence Chain", result.stdout)
        self.assertIn("contract.json", result.stdout)
        self.assertIn("task:", result.stdout)

    def test_missing_entrypoint_exits_two_with_hint(self) -> None:
        project_root = self._project(
            {"pyproject.toml": "[project]\nname = 'demo'\nversion = '0.1.0'\n"}
        )
        result = self.runner.invoke(
            app,
            ["init", "--path", str(project_root), "--data-dir", str(self.data_dir)],
        )
        self.assertEqual(result.exit_code, 2, result.output)
        self.assertIn("--no-bootstrap", result.stderr)
        self.assertIn("test.py", result.stderr)


if __name__ == "__main__":
    unittest.main()
