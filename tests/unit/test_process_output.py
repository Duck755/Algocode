from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from algocode.process_output import decode_process_output, run_text
from algocode.sandbox.runner import wsl_tool_version


class ProcessOutputTests(unittest.TestCase):
    def test_decodes_utf8(self) -> None:
        self.assertEqual(decode_process_output(b"hello"), "hello")

    def test_decodes_utf16le_without_bom(self) -> None:
        payload = "WSL version: 2.7.3".encode("utf-16-le")

        self.assertEqual(decode_process_output(payload), "WSL version: 2.7.3")

    def test_decodes_utf16_bom(self) -> None:
        payload = "WSL version: 2.7.3".encode("utf-16")

        self.assertEqual(decode_process_output(payload), "WSL version: 2.7.3")

    def test_invalid_bytes_use_replacement_instead_of_raising(self) -> None:
        decoded = decode_process_output(b"version\xff\xfe\x00")

        self.assertTrue(decoded)
        self.assertIn("version", decoded)

    def test_run_text_decodes_completed_process_output(self) -> None:
        completed = subprocess.CompletedProcess(
            args=("tool",),
            returncode=0,
            stdout="version 1.2.3".encode("utf-16-le"),
            stderr=b"",
        )
        with patch("algocode.process_output.subprocess.run", return_value=completed):
            result = run_text(("tool",), capture_output=True, check=False)

        self.assertEqual(result.stdout, "version 1.2.3")
        self.assertEqual(result.stderr, "")

    def test_wsl_tool_version_decodes_utf16_output(self) -> None:
        completed = subprocess.CompletedProcess(
            args=("wsl.exe",),
            returncode=0,
            stdout="g++ 13.2.0".encode("utf-16-le"),
            stderr=b"",
        )
        with (
            patch(
                "algocode.sandbox.runner.shutil.which",
                side_effect=lambda name: "wsl.exe" if name == "wsl.exe" else None,
            ),
            patch("algocode.process_output.subprocess.run", return_value=completed),
        ):
            version = wsl_tool_version("g++", "Ubuntu")

        self.assertEqual(version, "g++ 13.2.0")

    def test_run_text_allows_any_cwd_type(self) -> None:
        completed = subprocess.CompletedProcess(
            args=("git",),
            returncode=0,
            stdout=b"ok",
            stderr=b"",
        )
        with patch("algocode.process_output.subprocess.run", return_value=completed) as run:
            run_text(("git",), cwd=Path("."), check=True, capture_output=True)

        self.assertEqual(run.call_args.kwargs["cwd"], Path("."))


if __name__ == "__main__":
    unittest.main()
