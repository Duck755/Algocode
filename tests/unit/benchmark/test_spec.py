from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.benchmark.spec import (
    BenchmarkInputCase,
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

    def test_multi_input_requires_unique_ids(self) -> None:
        with self.assertRaises(ValueError):
            BenchmarkSpec(
                inputs=(
                    BenchmarkInputCase(id="same", input="a"),
                    BenchmarkInputCase(id="same", input="b"),
                ),
            )

    def test_single_input_and_matrix_are_mutually_exclusive(self) -> None:
        with self.assertRaises(ValueError):
            BenchmarkSpec(
                input="a",
                inputs=(BenchmarkInputCase(id="case", input="b"),),
            )

    def test_multi_input_changes_input_hash(self) -> None:
        single = BenchmarkSpec(input="a")
        multi = BenchmarkSpec(inputs=(BenchmarkInputCase(id="case", input="a"),))
        self.assertNotEqual(compute_input_hash(single), compute_input_hash(multi))
        self.assertEqual(multi.effective_inputs()[0].id, "case")


if __name__ == "__main__":
    unittest.main()
