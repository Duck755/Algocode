from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from algocode.cli.commands.doctor import run_doctor


class DoctorTests(unittest.TestCase):
    def test_report_is_json_serializable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = run_doctor(Path(directory))
            payload = json.loads(json.dumps(asdict(report)))
        self.assertEqual(payload["data_dir"], directory)
        names = {check["name"] for check in payload["checks"]}
        self.assertEqual(
            names,
            {"python", "git", "sqlite", "sandbox", "cpp_compiler", "data_dir"},
        )

    def test_data_directory_is_created(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nested" / "algocode"
            run_doctor(target)
            self.assertTrue(target.is_dir())


if __name__ == "__main__":
    unittest.main()
