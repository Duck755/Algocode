from __future__ import annotations

import unittest

from algocode.application.services.benchmark_service import (
    _comparison_from_payload,
    _result_from_payload,
    _sample_from_payload,
    _summary_from_payload,
)
from algocode.domain.model import BenchmarkMetric


class BenchmarkCacheHelpersTests(unittest.TestCase):
    def test_sample_and_summary_round_trip(self) -> None:
        sample = _sample_from_payload(
            {
                "target_kind": "candidate",
                "target_id": "c1",
                "phase": "measured",
                "index": 0,
                "input_id": "in1",
                "metric": "wall_time",
                "value": 1.5,
                "duration_seconds": 0.1,
                "exit_code": 0,
                "valid": True,
                "message": "",
            }
        )
        self.assertEqual(sample.metric, BenchmarkMetric.WALL_TIME)
        self.assertEqual(sample.value, 1.5)

        summary = _summary_from_payload(
            {
                "count": 2,
                "median": 1.5,
                "minimum": 1.0,
                "maximum": 2.0,
                "mean": 1.5,
                "stddev": 0.5,
                "variation_percent": 33.3,
            }
        )
        self.assertIsNotNone(summary)
        self.assertEqual(summary.count, 2)

    def test_result_and_comparison_rebuild_for_new_candidate(self) -> None:
        payload = {
            "target_kind": "candidate",
            "target_id": "old",
            "workspace_ref": "old-workspace",
            "workspace_hash": "old-hash",
            "spec_hash": "spec",
            "input_hash": "input",
            "environment_hash": "env",
            "comparison_key": "comparison",
            "valid": True,
            "message": "",
            "summary": {
                "count": 2,
                "median": 1.5,
                "minimum": 1.0,
                "maximum": 2.0,
                "mean": 1.5,
                "stddev": 0.5,
                "variation_percent": 33.3,
            },
            "baseline_summary": None,
            "candidate_summary": None,
            "comparison": None,
            "samples": [],
        }
        result = _result_from_payload(
            payload,
            target_id="new",
            workspace_ref="new-workspace",
            workspace_hash="new-hash",
        )
        self.assertEqual(result.target_id, "new")
        self.assertEqual(result.workspace_hash, "new-hash")

        comparison = _comparison_from_payload(
            {
                "baseline_run_id": "base-run",
                "candidate_run_id": "old-run",
                "baseline_id": "base",
                "candidate_id": "old",
                "comparison_key": "comparison",
                "baseline_median": 2.0,
                "candidate_median": 1.5,
                "improvement_percent": 25.0,
                "valid": True,
                "reason": "",
                "p_value": 0.01,
                "ci_lower": 0.1,
                "ci_upper": 0.2,
                "statistically_significant": True,
            },
            candidate_run_id="new-run",
            candidate_id="new",
        )
        self.assertEqual(comparison.candidate_run_id, "new-run")
        self.assertEqual(comparison.candidate_id, "new")
        self.assertEqual(comparison.improvement_percent, 25.0)


if __name__ == "__main__":
    unittest.main()
