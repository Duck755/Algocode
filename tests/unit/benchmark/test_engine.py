from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from algocode.benchmark.engine import (
    collect_interleaved_samples,
    run_benchmark_process,
)
from algocode.benchmark.spec import BenchmarkSpec


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


if __name__ == "__main__":
    unittest.main()
