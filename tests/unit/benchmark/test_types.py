from __future__ import annotations

import unittest

from algocode.benchmark.types import compare_sample_sets, summarize_values


class BenchmarkTypesTests(unittest.TestCase):
    def test_summarize_values_exposes_confidence_interval(self) -> None:
        summary = summarize_values([1.0, 1.1, 0.9, 1.2, 1.0])
        self.assertEqual(summary.count, 5)
        self.assertGreaterEqual(summary.ci_upper, summary.ci_lower)
        self.assertGreaterEqual(summary.trimmed_count, 0)

    def test_compare_sample_sets_reports_significance(self) -> None:
        comparison = compare_sample_sets(
            baseline_run_id="base-run",
            candidate_run_id="cand-run",
            baseline_id="base",
            candidate_id="cand",
            comparison_key="key",
            baseline_values=[1.0] * 15,
            candidate_values=[0.9] * 15,
            direction="minimize",
            max_variation_percent=None,
        )
        self.assertTrue(comparison.valid)
        self.assertGreater(comparison.improvement_percent, 0)
        self.assertLessEqual(comparison.p_value, 1.0)
        self.assertGreaterEqual(comparison.ci_upper, comparison.ci_lower)

    def test_compare_sample_sets_rejects_noise_threshold(self) -> None:
        comparison = compare_sample_sets(
            baseline_run_id="base-run",
            candidate_run_id="cand-run",
            baseline_id="base",
            candidate_id="cand",
            comparison_key="key",
            baseline_values=[1.0, 1.2, 0.8, 1.4, 0.6],
            candidate_values=[1.1, 0.7, 1.3, 0.5, 1.5],
            direction="minimize",
            max_variation_percent=5.0,
        )
        self.assertFalse(comparison.valid)
        self.assertIn("variation", comparison.reason)


if __name__ == "__main__":
    unittest.main()
