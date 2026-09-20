from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from algocode.application.services.decision_service import (
    DecisionService,
    _algorithmic_gain,
)
from algocode.config.model import AcceptancePolicyConfig
from algocode.domain.model import (
    ArtifactRef,
    BenchmarkStatus,
    CandidateStatus,
    CorrectnessStatus,
    DecisionOutcome,
)
from algocode.security import SecretRedactor
from algocode.storage.events import SqliteEventStore
from algocode.storage.sqlite.database import Database
from algocode.storage.sqlite.projections.candidate_projection import CandidateProjection
from algocode.storage.sqlite.projections.decision_projection import DecisionProjection


class DecisionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database = Database(self.root / "data")
        self.database.initialize()
        self.candidate_projection = CandidateProjection()
        self.decision_projection = DecisionProjection()
        self.event_store = SqliteEventStore(
            self.database,
            projectors=(self.candidate_projection, self.decision_projection),
            redactor=SecretRedactor(),
        )
        now = datetime.now(UTC).isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO tasks(
                    id, project_id, objective, status, current_phase,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("task-1", "project-1", "objective", "running", "decide", now, now),
            )
            connection.execute(
                """
                INSERT INTO candidates(
                    id, task_id, base_revision, base_snapshot_hash,
                    workspace_ref, status, created_at, frozen_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("candidate-1", "task-1", "base", "snapshot", "workspace", "frozen", now, now),
            )

        self.candidate_service = SimpleNamespace(
            get=AsyncMock(
                return_value=SimpleNamespace(task_id="task-1", id="candidate-1", frozen_at=now)
            )
        )
        self.task_service = SimpleNamespace(
            get_task=AsyncMock(return_value=SimpleNamespace(id="task-1"))
        )
        self.correctness_service = SimpleNamespace(
            list_for_task=AsyncMock(return_value=[]),
        )
        self.benchmark_service = SimpleNamespace(
            list_for_task=AsyncMock(return_value=[]),
            read_result=AsyncMock(return_value={}),
            read_comparison=AsyncMock(return_value=None),
        )
        self.service = DecisionService(
            event_store=self.event_store,
            database=self.database,
            task_service=self.task_service,
            candidate_service=self.candidate_service,
            correctness_service=self.correctness_service,
            benchmark_service=self.benchmark_service,
            decision_projection=self.decision_projection,
            acceptance_policy=AcceptancePolicyConfig(),
        )

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _candidate_correctness(self) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(
                target_kind="candidate",
                target_id="candidate-1",
                status=CorrectnessStatus.PASSED,
                result_ref=ArtifactRef(uri="correctness", sha256="a" * 64),
            )
        ]

    def _candidate_benchmark(
        self,
        improvement_percent: float,
        statistically_significant: bool,
        variation_percent: float = 1.0,
    ) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(
                target_kind="candidate",
                target_id="candidate-1",
                status=BenchmarkStatus.COMPLETED,
                result_ref=ArtifactRef(uri="result", sha256="b" * 64),
                comparison_ref=ArtifactRef(uri="comparison", sha256="c" * 64),
            )
        ]

    def _set_benchmark_evidence(
        self,
        improvement_percent: float,
        statistically_significant: bool,
    ) -> None:
        self.correctness_service.list_for_task.return_value = self._candidate_correctness()
        self.benchmark_service.list_for_task.return_value = self._candidate_benchmark(
            improvement_percent,
            statistically_significant,
        )
        self.benchmark_service.read_result.return_value = {
            "baseline_summary": {"robust_variation_percent": 1.0},
            "candidate_summary": {"robust_variation_percent": 1.0},
        }
        self.benchmark_service.read_comparison.return_value = {
            "valid": True,
            "improvement_percent": improvement_percent,
            "statistically_significant": statistically_significant,
            "p_value": 0.01 if statistically_significant else 0.8,
            "pairing": "paired",
            "ci_lower": 1.0 if statistically_significant else -1.0,
            "ci_upper": 10.0 if statistically_significant else 1.0,
        }

    async def test_auto_decide_rejects_negative_improvement(self) -> None:
        self._set_benchmark_evidence(-3.0, True)
        decision = await self.service.auto_decide("task-1", "candidate-1")
        self.assertEqual(decision.outcome, DecisionOutcome.REJECTED)
        with self.database.connect() as connection:
            candidate = self.candidate_projection.get(connection, "candidate-1")
        self.assertEqual(candidate.status, CandidateStatus.REJECTED)

    async def test_auto_decide_marks_noise_inconclusive(self) -> None:
        self._set_benchmark_evidence(5.0, False)
        decision = await self.service.auto_decide("task-1", "candidate-1")
        self.assertEqual(decision.outcome, DecisionOutcome.INCONCLUSIVE)
        with self.database.connect() as connection:
            candidate = self.candidate_projection.get(connection, "candidate-1")
        self.assertEqual(candidate.status, CandidateStatus.INCONCLUSIVE)

    async def test_auto_decide_accepts_significant_improvement(self) -> None:
        self._set_benchmark_evidence(5.0, True)
        decision = await self.service.auto_decide("task-1", "candidate-1")
        self.assertEqual(decision.outcome, DecisionOutcome.ACCEPTED)
        with self.database.connect() as connection:
            candidate = self.candidate_projection.get(connection, "candidate-1")
        self.assertEqual(candidate.status, CandidateStatus.SELECTED)

    async def test_legacy_quality_warnings_do_not_pollute_accepted_reason(self) -> None:
        self._set_benchmark_evidence(5.0, True)
        self.benchmark_service.read_comparison.return_value["quality_warnings"] = [
            "raw sample variation exceeded configured threshold"
        ]

        decision = await self.service.auto_decide("task-1", "candidate-1")

        self.assertEqual(decision.outcome, DecisionOutcome.ACCEPTED)
        self.assertEqual(
            decision.reason,
            "correctness and benchmark evidence passed acceptance policy",
        )


class AlgorithmicGainTests(unittest.TestCase):
    def test_accepts_a_large_enough_exponent_drop(self) -> None:
        policy = AcceptancePolicyConfig()

        self.assertTrue(_algorithmic_gain({"growth_delta": 0.9, "growth_points": 4}, policy))

    def test_requires_enough_size_points(self) -> None:
        policy = AcceptancePolicyConfig()

        self.assertFalse(_algorithmic_gain({"growth_delta": 0.9, "growth_points": 2}, policy))

    def test_rejects_a_small_exponent_drop(self) -> None:
        policy = AcceptancePolicyConfig()

        self.assertFalse(_algorithmic_gain({"growth_delta": 0.1, "growth_points": 4}, policy))

    def test_missing_evidence_grants_nothing(self) -> None:
        policy = AcceptancePolicyConfig()

        self.assertFalse(_algorithmic_gain({}, policy))
        self.assertFalse(
            _algorithmic_gain({"growth_delta": None, "growth_points": None}, policy)
        )

    def test_disabled_policy_never_grants_the_waiver(self) -> None:
        policy = AcceptancePolicyConfig(growth_points_required=0)

        self.assertFalse(_algorithmic_gain({"growth_delta": 2.0, "growth_points": 4}, policy))


if __name__ == "__main__":
    unittest.main()
