from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from algocode.benchmark.engine import (
    collect_interleaved_samples,
    run_benchmark_process,
)
from algocode.benchmark.spec import BenchmarkInputCase, BenchmarkSpec
from algocode.domain.model import BenchmarkMetric


def _python(code: str) -> tuple[str, ...]:
    return (sys.executable, "-c", code)


class BenchmarkEngineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary_directory.name)

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_median_and_sample_count(self) -> None:
        spec = BenchmarkSpec(
            run_command=_python("import time; time.sleep(0.01)"),
            warmup=2,
            repeats=5,
        )

        result = await run_benchmark_process(self.workspace, spec)

        self.assertTrue(result.valid)
        self.assertEqual(len(result.samples), 7)
        self.assertEqual(result.summary.count, 5)
        self.assertGreater(result.summary.median, 0)

    async def test_interleaved_measurements_alternate_targets(self) -> None:
        baseline = BenchmarkSpec(
            run_command=_python("import time; time.sleep(0.01)"),
            warmup=1,
            repeats=2,
        )
        candidate = BenchmarkSpec(
            run_command=_python("import time; time.sleep(0.005)"),
            warmup=1,
            repeats=2,
        )

        samples = await collect_interleaved_samples(
            self.workspace,
            self.workspace,
            baseline,
            candidate,
            baseline_id="base",
            candidate_id="cand",
        )
        measured = [sample.target_kind for sample in samples if sample.phase == "measured"]

        self.assertEqual(measured, ["baseline", "candidate", "candidate", "baseline"])

    async def test_measured_failure_marks_result_invalid(self) -> None:
        spec = BenchmarkSpec(
            run_command=_python("raise SystemExit(2)"),
            warmup=0,
            repeats=1,
        )

        result = await run_benchmark_process(self.workspace, spec)

        self.assertFalse(result.valid)
        self.assertFalse(result.samples[0].valid)

    async def test_multi_input_matrix_collects_each_case(self) -> None:
        spec = BenchmarkSpec(
            run_command=_python("import sys; sys.stdin.read()"),
            scope="stdin",
            inputs=(
                BenchmarkInputCase(id="small", input="1"),
                BenchmarkInputCase(id="large", input="2"),
            ),
            warmup=0,
            repeats=2,
        )

        result = await run_benchmark_process(self.workspace, spec)

        measured = [sample for sample in result.samples if sample.phase == "measured"]
        self.assertEqual(len(measured), 4)
        self.assertEqual([sample.input_id for sample in measured], ["small", "small", "large", "large"])

    async def test_peak_memory_metric_is_recorded_when_available(self) -> None:
        spec = BenchmarkSpec(
            run_command=_python("x = [0] * 10000"),
            warmup=0,
            repeats=1,
            metric=BenchmarkMetric.PEAK_MEMORY,
        )

        result = await run_benchmark_process(self.workspace, spec)

        if not result.valid:
            self.skipTest("peak_memory is unavailable on this sandbox backend")
        self.assertEqual(result.samples[0].metric, BenchmarkMetric.PEAK_MEMORY)
        self.assertGreater(result.samples[0].value, 0)


if __name__ == "__main__":
    unittest.main()
