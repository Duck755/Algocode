from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.runtime.analysis import ReadCoverage, discover_required_files, parse_analysis_report


class AnalysisCoverageTests(unittest.TestCase):
    def test_discovery_ignores_venv_binary_and_large_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.py").write_text("print('hello')\n", encoding="utf-8")
            (root / ".algocode.yaml").write_text("version: 1\n", encoding="utf-8")
            (root / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
            (root / ".venv").mkdir()
            (root / ".venv" / "ignored.py").write_text("print('ignored')\n", encoding="utf-8")
            (root / "binary.bin").write_bytes(b"\x00\x01\x02")
            (root / "large.py").write_text("x" * 200_001, encoding="utf-8")

            required = discover_required_files(root)

        self.assertEqual(required, (".algocode.yaml", "main.py"))

    def test_two_distinct_turn_reads_are_required(self) -> None:
        coverage = ReadCoverage(("main.py",))
        coverage.record_read("main.py", 1)
        self.assertFalse(coverage.complete)

        coverage.record_read("main.py", 1)
        self.assertFalse(coverage.complete)

        coverage.record_read("main.py", 2)
        self.assertTrue(coverage.complete)

    def test_analysis_report_accepts_json_code_fence(self) -> None:
        report = parse_analysis_report(
            """```json
            {
              "summary": "Project analyzed",
              "language": "python",
              "files": [{"path": "main.py", "role": "algorithm"}],
              "optimizationCandidates": [
                {"id": "dijkstra", "description": "Use repeated Dijkstra"}
              ]
            }
            ```"""
        )

        self.assertEqual(report.language, "python")
        self.assertEqual(report.optimization_candidates[0].id, "dijkstra")

    def test_analysis_report_normalizes_string_entrypoint_commands(self) -> None:
        report = parse_analysis_report(
            '{"summary": "Project analyzed", "entrypointCommands": '
            '["python test.py", ["python", "-m", "test"]]}'
        )

        self.assertEqual(
            report.entrypoint_commands,
            (("python", "test.py"), ("python", "-m", "test")),
        )


if __name__ == "__main__":
    unittest.main()
