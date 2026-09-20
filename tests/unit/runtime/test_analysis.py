from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from algocode.runtime.analysis import ReadCoverage, discover_required_files, parse_analysis_report


def _report(**overrides: object) -> str:
    """A minimal but complete analysis report, as JSON text."""

    payload: dict[str, object] = {
        "summary": "Project analyzed",
        "language": "python",
        "files": [{"path": "main.py", "role": "algorithm"}],
        "problemStructure": {
            "inputModel": "stdin with n values",
            "dataDistribution": "uniform integers",
            "operationAlgebra": "min is associative and commutative",
            "queryUpdateMix": "read-only queries",
            "monotonicity": "weights are non-negative",
            "constraints": ["output order preserved"],
        },
        "complexityBaseline": {
            "current": "O(n^3)",
            "knownBest": "O(n^2 log n)",
            "gap": "the all-pairs matrix is rebuilt per query",
            "reasoning": "reusing the previous tree avoids the rebuild",
        },
        "algorithmCandidates": [
            {
                "name": "repeated Dijkstra",
                "paradigm": "shortest path",
                "complexity": "O(n^2 log n)",
                "applicability": "non-negative weights",
                "expectedGain": "removes the cubic rebuild",
            },
            {
                "name": "Floyd-Warshall",
                "paradigm": "dynamic programming",
                "complexity": "O(n^3)",
                "applicability": "dense graphs",
                "expectedGain": "simpler but no asymptotic gain",
            },
            {
                "name": "BFS layering",
                "paradigm": "graph traversal",
                "complexity": "O(n+m)",
                "applicability": "unit weights only",
                "expectedGain": "linear when weights are uniform",
            },
        ],
        "optimizationCandidates": [
            {"id": "dijkstra", "description": "Use repeated Dijkstra"}
        ],
    }
    payload.update(overrides)
    return json.dumps(payload)


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
        report = parse_analysis_report(f"```json\n{_report()}\n```")

        self.assertEqual(report.language, "python")
        self.assertEqual(report.optimization_candidates[0].id, "dijkstra")
        self.assertEqual(report.complexity_baseline.current, "O(n^3)")
        self.assertEqual(len(report.algorithm_candidates), 3)

    def test_analysis_report_normalizes_string_entrypoint_commands(self) -> None:
        report = parse_analysis_report(
            _report(entrypointCommands=["python test.py", ["python", "-m", "test"]])
        )

        self.assertEqual(
            report.entrypoint_commands,
            (("python", "test.py"), ("python", "-m", "test")),
        )


    def test_analysis_report_rejects_missing_problem_structure(self) -> None:
        with self.assertRaises(ValueError) as caught:
            parse_analysis_report(_report(problemStructure=None))

        self.assertIn("problemStructure", str(caught.exception))

    def test_analysis_report_rejects_empty_structure_field(self) -> None:
        with self.assertRaises(ValueError) as caught:
            parse_analysis_report(
                _report(
                    problemStructure={
                        "inputModel": "",
                        "dataDistribution": "uniform",
                        "operationAlgebra": "associative",
                        "queryUpdateMix": "read-only",
                        "monotonicity": "none",
                    }
                )
            )

        self.assertIn("problemStructure.inputModel", str(caught.exception))

    def test_analysis_report_requires_three_algorithm_candidates(self) -> None:
        with self.assertRaises(ValueError) as caught:
            parse_analysis_report(
                _report(
                    algorithmCandidates=[
                        {
                            "name": "only one",
                            "paradigm": "sorting",
                            "complexity": "O(n log n)",
                            "applicability": "always",
                        }
                    ]
                )
            )

        self.assertIn("at least 3", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
