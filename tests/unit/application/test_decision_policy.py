from __future__ import annotations

import unittest

from algocode.application.services.decision_service import DecisionService
from algocode.config.model import AcceptancePolicyConfig
from algocode.domain.errors import DecisionError


class AcceptancePolicyTests(unittest.TestCase):
    def _service(self, policy: AcceptancePolicyConfig) -> DecisionService:
        return DecisionService(
            event_store=object(),
            database=object(),
            task_service=object(),
            candidate_service=object(),
            correctness_service=object(),
            benchmark_service=object(),
            decision_projection=object(),
            acceptance_policy=policy,
        )

    def test_rejects_improvement_below_threshold(self) -> None:
        service = self._service(AcceptancePolicyConfig(min_median_improvement_percent=5.0))

        with self.assertRaisesRegex(DecisionError, "below the acceptance threshold"):
            service._validate_acceptance_thresholds(
                {},
                {"valid": True, "improvement_percent": 4.9},
            )

    def test_rejects_excessive_variation(self) -> None:
        service = self._service(AcceptancePolicyConfig(max_variation_percent=5.0))

        with self.assertRaisesRegex(DecisionError, "variation exceeds"):
            service._validate_acceptance_thresholds(
                {
                    "baseline_summary": {"variation_percent": 6.0},
                    "candidate_summary": {"variation_percent": 1.0},
                },
                {"valid": True, "improvement_percent": 10.0},
            )

    def test_accepts_valid_policy_result(self) -> None:
        service = self._service(
            AcceptancePolicyConfig(
                min_median_improvement_percent=2.0,
                max_variation_percent=5.0,
            )
        )

        service._validate_acceptance_thresholds(
            {
                "baseline_summary": {"variation_percent": 1.0},
                "candidate_summary": {"variation_percent": 2.0},
            },
            {
                "valid": True,
                "improvement_percent": 3.0,
                "statistically_significant": True,
                "p_value": 0.01,
            },
        )

    def test_rejects_improvement_without_statistical_significance(self) -> None:
        service = self._service(AcceptancePolicyConfig(min_median_improvement_percent=-1000.0))

        with self.assertRaisesRegex(DecisionError, "not statistically significant"):
            service._validate_acceptance_thresholds(
                {},
                {
                    "valid": True,
                    "improvement_percent": 10.0,
                    "statistically_significant": False,
                    "p_value": 0.8,
                },
            )


if __name__ == "__main__":
    unittest.main()
