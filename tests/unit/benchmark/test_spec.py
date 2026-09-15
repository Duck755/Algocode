from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.benchmark.spec import (
    BenchmarkSpec,
    compute_benchmark_spec_hash,
    compute_comparison_key,
    compute_input_hash,
    load_benchmark_spec,
)
from algocode.domain.errors import ConfigError
from algocode.domain.model import BenchmarkMetric


class BenchmarkSpecTests(unittest.TestCase):
    def test_load_and_hashes_are_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "benchmark.yaml"
            path.write_text(
                """
scope: stdin
input: "hello"
warmup: 2
repeats: 5
""",
                encoding="utf-8",
            )
            first = load_benchmark_spec(path)
            second = load_benchmark_spec(path)

        self.assertEqual(first.metric, BenchmarkMetric.WALL_TIME)
        self.assertEqual(compute_benchmark_spec_hash(first), compute_benchmark_spec_hash(second))
        self.assertEqual(compute_input_hash(first), compute_input_hash(second))
        self.assertEqual(
            compute_comparison_key(
                spec_hash=compute_benchmark_spec_hash(first),
                input_hash=compute_input_hash(first),
                environment_hash="env",
            ),
            compute_comparison_key(
                spec_hash=compute_benchmark_spec_hash(second),
                input_hash=compute_input_hash(second),
                environment_hash="env",
            ),
        )

    def test_function_scope_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            BenchmarkSpec(scope="function")

    def test_non_mapping_spec_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "benchmark.yaml"
            path.write_text("- invalid\n", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_benchmark_spec(path)


if __name__ == "__main__":
    unittest.main()
