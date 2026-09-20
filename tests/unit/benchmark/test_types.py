from __future__ import annotations

import unittest

from algocode.benchmark.types import (
    compare_sample_sets,
    estimate_growth,
    summarize_values,
)


class BenchmarkTypesTests(unittest.TestCase):
    def test_summarize_values_exposes_confidence_interval(self) -> None:
        summary = summarize_values([1.0, 1.1, 0.9, 1.2, 1.0])
        self.assertEqual(summary.count, 5)
        self.assertGreaterEqual(summary.ci_upper, summary.ci_lower)
        self.assertGreaterEqual(summary.trimmed_count, 0)
        self.assertGreaterEqual(summary.robust_variation_percent, 0.0)

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


    def test_single_outlier_does_not_create_quality_warning(self) -> None:
        baseline = [
            0.554469,
            0.552764,
            0.551170,
            0.546834,
            0.544849,
            0.561881,
            0.568761,
            0.540253,
            0.560704,
            0.542253,
            0.593427,
            0.554050,
            0.566324,
            0.555111,
            0.568631,
        ]
        candidate = [
            0.320795,
            0.320966,
            0.343243,
            0.312331,
            0.315939,
            0.312343,
            0.727158,
            0.342526,
            0.316601,
            0.312803,
            0.331190,
            0.321406,
            0.327348,
            0.313042,
            0.334615,
        ]
        comparison = compare_sample_sets(
            baseline_run_id="base-run",
            candidate_run_id="cand-run",
            baseline_id="base",
            candidate_id="cand",
            comparison_key="key",
            baseline_values=baseline,
            candidate_values=candidate,
            direction="minimize",
            max_variation_percent=15.0,
        )

        self.assertTrue(comparison.valid)
        self.assertEqual(comparison.quality_warnings, ())
        self.assertEqual(comparison.pairing, "paired")
        self.assertGreater(comparison.improvement_percent, 40.0)
        self.assertTrue(comparison.statistically_significant)
        self.assertGreater(comparison.ci_lower, 0.0)


class GrowthEstimateTests(unittest.TestCase):
    def test_quadratic_growth_is_recovered(self) -> None:
        estimate = estimate_growth([(1000, 1.0), (2000, 4.0), (4000, 16.0), (8000, 64.0)])

        self.assertIsNotNone(estimate)
        self.assertAlmostEqual(estimate.exponent, 2.0, places=6)
        self.assertEqual(estimate.points, 4)
        self.assertGreater(estimate.r_squared, 0.99)

    def test_linear_growth_has_exponent_one(self) -> None:
        estimate = estimate_growth([(1000, 2.0), (4000, 8.0)])

        self.assertIsNotNone(estimate)
        self.assertAlmostEqual(estimate.exponent, 1.0, places=6)

    def test_unsuitable_points_are_rejected(self) -> None:
        self.assertIsNone(estimate_growth([(1000, 1.0)]))
        self.assertIsNone(estimate_growth([(1000, 1.0), (2000, 0.0)]))
        self.assertIsNone(estimate_growth([(1, 1.0), (1, 2.0)]))


class GroupedComparisonTests(unittest.TestCase):
    def _compare(self, baseline, candidate, sizes):
        return compare_sample_sets(
            baseline_run_id="base-run",
            candidate_run_id="cand-run",
            baseline_id="base",
            candidate_id="cand",
            comparison_key="key",
            baseline_values=tuple(value for group in baseline.values() for value in group),
            candidate_values=tuple(value for group in candidate.values() for value in group),
            direction="minimize",
            max_variation_percent=5.0,
            baseline_groups=baseline,
            candidate_groups=candidate,
            input_sizes=sizes,
        )

    def test_reports_per_input_improvements(self) -> None:
        comparison = self._compare(
            {"n1k": [1.0] * 5, "n4k": [16.0] * 5},
            {"n1k": [2.0] * 5, "n4k": [8.0] * 5},
            {"n1k": 1000, "n4k": 4000},
        )

        self.assertEqual(len(comparison.per_input), 2)
        self.assertAlmostEqual(comparison.improvement_percent, -25.0, places=6)

    def test_growth_drop_is_detected_across_sizes(self) -> None:
        comparison = self._compare(
            {"n1k": [1.0] * 5, "n2k": [4.0] * 5, "n4k": [16.0] * 5},
            {"n1k": [2.0] * 5, "n2k": [4.0] * 5, "n4k": [8.0] * 5},
            {"n1k": 1000, "n2k": 2000, "n4k": 4000},
        )

        self.assertAlmostEqual(comparison.growth_baseline, 2.0, places=6)
        self.assertAlmostEqual(comparison.growth_candidate, 1.0, places=6)
        self.assertAlmostEqual(comparison.growth_delta, 1.0, places=6)
        self.assertEqual(comparison.growth_points, 3)

    def test_worst_input_variation_decides_validity(self) -> None:
        comparison = self._compare(
            {"n1k": [1.0] * 5, "n4k": [0.5, 1.0, 1.5, 2.0, 2.5]},
            {"n1k": [1.0] * 5, "n4k": [1.0] * 5},
            {"n1k": 1000, "n4k": 4000},
        )

        self.assertFalse(comparison.valid)
        self.assertIn("variation", comparison.reason)


if __name__ == "__main__":
    unittest.main()
