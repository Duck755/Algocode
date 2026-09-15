from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

from algocode.cli.main import app


class CliEvalTests(unittest.TestCase):
    def test_smoke_eval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = CliRunner().invoke(
                app,
                [
                    "eval",
                    "run",
                    "smoke",
                    "--provider",
                    "fake",
                    "--data-dir",
                    str(Path(directory) / "data"),
                    "--json",
                ],
            )

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["data"]["aggregate"]["pass_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
