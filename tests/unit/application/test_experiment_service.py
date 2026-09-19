from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from algocode.application.services.experiment_service import ExperimentService
from algocode.domain.model import DecisionOutcome, ExperimentStatus
from algocode.security import SecretRedactor
from algocode.storage.events import SqliteEventStore
from algocode.storage.sqlite.database import Database
from algocode.storage.sqlite.projections.experiment_projection import ExperimentProjection


class ExperimentServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database = Database(self.root / "data")
        self.database.initialize()
        self.projection = ExperimentProjection()
        self.event_store = SqliteEventStore(
            self.database,
            projectors=(self.projection,),
            redactor=SecretRedactor(),
        )
        self.service = ExperimentService(
            event_store=self.event_store,
            database=self.database,
            experiment_projection=self.projection,
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
                    workspace_ref, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("candidate-1", "task-1", "base", "snapshot", "workspace", "frozen", now),
            )

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_lifecycle_is_persisted(self) -> None:
        experiment = await self.service.create(
            "task-1",
            candidate_id="candidate-1",
            baseline_id="baseline-1",
            spec_hash="spec",
            input_hash="input",
            environment_hash="env",
            comparison_key="comparison",
            policy_hash="policy",
        )
        self.assertEqual(experiment.status, ExperimentStatus.CREATED)

        experiment = await self.service.start(experiment.id)
        self.assertEqual(experiment.status, ExperimentStatus.RUNNING)
        self.assertIsNotNone(experiment.started_at)

        experiment = await self.service.complete(
            experiment.id,
            decision=DecisionOutcome.REJECTED,
        )
        self.assertEqual(experiment.status, ExperimentStatus.COMPLETED)
        self.assertEqual(experiment.decision, DecisionOutcome.REJECTED)
        self.assertIsNotNone(experiment.completed_at)

        reloaded = await self.service.get_for_candidate("candidate-1")
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.id, experiment.id)


if __name__ == "__main__":
    unittest.main()
