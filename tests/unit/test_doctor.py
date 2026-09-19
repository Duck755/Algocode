from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from algocode.cli.commands.doctor import (
    DoctorCheck,
    DoctorReport,
    _host_install_command,
    _missing_install_dependencies,
    run_doctor,
)


class DoctorTests(unittest.TestCase):
    def test_report_is_json_serializable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = run_doctor(Path(directory))
            payload = json.loads(json.dumps(asdict(report)))
        self.assertEqual(payload["data_dir"], directory)
        names = {check["name"] for check in payload["checks"]}
        base_names = {"python", "cpp_compiler", "git", "sqlite", "sandbox", "data_dir"}
        self.assertTrue(base_names <= names)
        for name in names - base_names:
            self.assertRegex(name, r"^(docker|wsl) (g\+\+|python)$")

    def test_data_directory_is_created(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nested" / "algocode"
            run_doctor(target)
            self.assertTrue(target.is_dir())

    def test_missing_dependencies_ignore_sandbox_backend_itself(self) -> None:
        report = DoctorReport(
            ok=True,
            version="0.1.1",
            python="3.13",
            platform="windows",
            data_dir="",
            checks=(
                DoctorCheck("sandbox", "warn", "native only"),
                DoctorCheck("cpp_compiler", "warn", "no compiler"),
                DoctorCheck("docker g++", "warn", "not found"),
                DoctorCheck("wsl python", "error", "not found"),
                DoctorCheck("git", "ok", "git"),
            ),
        )
        keys = {item.key for item in _missing_install_dependencies(report)}
        self.assertEqual(keys, {"cpp_compiler", "docker_g++", "wsl_python"})

    def test_sqlite_install_uses_pip(self) -> None:
        command = _host_install_command("sqlite", None)
        self.assertIsNotNone(command)
        self.assertEqual(command[:3], (sys.executable, "-m", "pip"))
        self.assertIn("pysqlite3", command)


if __name__ == "__main__":
    unittest.main()
