from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.correctness.spec import CorrectnessSpec, compute_spec_hash, load_correctness_spec
from algocode.domain.errors import ConfigError
from algocode.domain.model import ComparisonMode, CorrectnessMode


class CorrectnessSpecTests(unittest.TestCase):
    def test_load_spec_and_hash_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "correctness.yaml"
            path.write_text(
                """
mode: cases
run_command: ["python", "main.py"]
comparison: exact
cases:
  - id: case-1
    input: "1 2"
    expected_output: "3"
    expected_exit_code: 0
""",
                encoding="utf-8",
            )
            first = load_correctness_spec(path)
            second = load_correctness_spec(path)

        self.assertEqual(first.mode, CorrectnessMode.CASES)
        self.assertEqual(first.comparison, ComparisonMode.EXACT)
        self.assertEqual(compute_spec_hash(first), compute_spec_hash(second))

    def test_invalid_mode_configuration_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CorrectnessSpec(mode=CorrectnessMode.ORACLE)

    def test_checker_comparison_requires_checker_command(self) -> None:
        with self.assertRaises(ValueError):
            CorrectnessSpec(
                mode=CorrectnessMode.CASES,
                cases=({"id": "one"},),
                comparison=ComparisonMode.CHECKER_COMMAND,
            )

    def test_non_mapping_spec_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "correctness.yaml"
            path.write_text("- invalid\n", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_correctness_spec(path)


if __name__ == "__main__":
    unittest.main()
