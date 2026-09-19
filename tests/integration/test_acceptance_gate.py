"""Acceptance gate integration tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.acceptance import AcceptanceService


class AcceptanceGateTests(unittest.TestCase):
    def test_gate_generates_zero_failure_report(self) -> None:
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            report_dir = Path(directory) / "report"
            report = AcceptanceService(root, report_dir=report_dir).run(run_tests=False)

            failed = [check.id for check in report.checks if not check.passed]
            self.assertEqual(report.status, "PASS", failed)
            self.assertEqual(report.metrics["false_accept_count"], 0)
            self.assertEqual(report.metrics["policy_violation_count"], 0)
            self.assertEqual(report.metrics["protected_file_change_count"], 0)
            self.assertEqual(report.metrics["replay_divergence_count"], 0)
            self.assertEqual(report.metrics["event_sequence_gap_count"], 0)
            self.assertEqual(report.metrics["apply_rollback_failure_count"], 0)
            self.assertEqual(report.metrics["noise_false_accept_count"], 0)
            self.assertEqual(report.metrics["minimal_gain_detection_count"], 1)
            self.assertTrue((report_dir / "report.json").exists())
            self.assertTrue((report_dir / "report.md").exists())


if __name__ == "__main__":
    unittest.main()

