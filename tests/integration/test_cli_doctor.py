from __future__ import annotations

import json
import unittest

from typer.testing import CliRunner

from algocode import __version__
from algocode.cli.main import app


class CliDoctorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_version(self) -> None:
        result = self.runner.invoke(app, ["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout.strip(), __version__)

    def test_doctor_json(self) -> None:
        result = self.runner.invoke(app, ["doctor", "--json"])
        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.stdout)["data"]
        self.assertEqual(payload["version"], __version__)
        self.assertIn("checks", payload)


if __name__ == "__main__":
    unittest.main()
