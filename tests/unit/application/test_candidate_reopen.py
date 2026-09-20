from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from algocode.application.services.candidate_service import CandidateService
from algocode.domain.events import EventType
from algocode.domain.model import CandidateStatus
from algocode.security import SecretRedactor
from algocode.storage.events import SqliteEventStore
from algocode.storage.sqlite.database import Database
from algocode.storage.sqlite.projections.candidate_projection import CandidateProjection


class CandidateReopenTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.database = Database(root / "data")
        self.database.initialize()
        self.projection = CandidateProjection()
        self.event_store = SqliteEventStore(
            self.database,
            projectors=(self.projection,),
            redactor=SecretRedactor(),
        )
        self.service = CandidateService(
            event_store=self.event_store,
            database=self.database,
            task_service=object(),
            project_service=object(),
            baseline_service=object(),
            candidate_projection=self.projection,
            data_dir=root / "data",
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
                (
                    "task-1",
                    "project-1",
                    "objective",
                    "waiting_user",
                    "implement",
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO candidates(
                    id,
                    task_id,
                    base_revision,
                    base_snapshot_hash,
                    workspace_ref,
                    status,
                    patch_hash,
                    created_at,
                    frozen_at,
                    parent_candidate_id,
                    fork_snapshot_hash,
                    apply_base_revision,
                    apply_base_snapshot_hash
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "candidate-1",
                    "task-1",
                    "revision",
                    "base-snapshot",
                    "workspace",
                    CandidateStatus.INCONCLUSIVE.value,
                    "patch",
                    now,
                    now,
                    None,
                    "base-snapshot",
                    "revision",
                    "base-snapshot",
                ),
            )

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_reopen_moves_decided_candidate_back_to_editing(self) -> None:
        reopened = await self.service.reopen("candidate-1")

        self.assertEqual(reopened.status, CandidateStatus.EDITING)
        self.assertIsNone(reopened.frozen_at)
        events = await self.event_store.read("task-1")
        self.assertEqual(events[-1].type, EventType.CANDIDATE_REOPENED)
        self.assertEqual(events[-1].payload["candidate_id"], "candidate-1")


if __name__ == "__main__":
    unittest.main()
