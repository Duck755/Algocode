from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.config import load_config
from algocode.eval.service import EvalService


class EvalServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.config = load_config(
            project_root=self.root,
            data_dir=self.root / "data",
            environ={},
        )
        self.service = EvalService(self.config, self.root / "data")

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_builtin_suites_pass(self) -> None:
        for suite_name in ("smoke", "core", "adversarial", "recovery"):
            run = await self.service.run(suite_name, provider="auto")
            self.assertEqual(run.aggregate["pass_rate"], 1.0, suite_name)

    async def test_ab_compare_and_report_persistence(self) -> None:
        baseline, candidate, comparison = await self.service.compare(
            "smoke",
            baseline_provider="fake",
            candidate_provider="fake",
        )

        self.assertEqual(baseline.aggregate["pass_rate"], 1.0)
        self.assertEqual(candidate.aggregate["pass_rate"], 1.0)
        self.assertEqual(comparison.pass_rate_delta, 0.0)
        self.assertTrue((self.service.report_dir / f"{baseline.run_id}.json").exists())
        self.assertTrue((self.service.report_dir / f"{candidate.run_id}.md").exists())


if __name__ == "__main__":
    unittest.main()
