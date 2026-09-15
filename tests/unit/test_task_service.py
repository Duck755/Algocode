from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.application.services import TaskService
from algocode.bootstrap import build_context
from algocode.domain.errors import NotFoundError
from algocode.domain.events import EventType
from algocode.domain.model import TaskPhase, TaskStatus
from algocode.storage.events import SqliteEventStore
from algocode.storage.sqlite import Database
from algocode.storage.sqlite.projections.task_projection import TaskProjection


class TaskServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temporary_directory.name)
        self.context = build_context(data_dir=self.data_dir)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_create_and_restore_task(self) -> None:
        created = await self.context.task_service.create_task("  Optimize matmul  ")

        self.assertEqual(created.objective, "Optimize matmul")
        self.assertEqual(created.status, TaskStatus.DRAFT)
        self.assertEqual(created.current_phase, TaskPhase.CREATE)

        restored = await self.context.task_service.get_task(created.id)
        self.assertEqual(restored, created)
        self.assertEqual(await self.context.task_service.list_tasks(), [created])

        events = await self.context.event_store.read(str(created.id))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, EventType.TASK_CREATED)
        self.assertEqual(events[0].payload["objective"], "Optimize matmul")

    async def test_read_model_survives_new_context(self) -> None:
        created = await self.context.task_service.create_task("Optimize sorted search")
        restarted = build_context(data_dir=self.data_dir)

        restored = await restarted.task_service.get_task(created.id)
        self.assertEqual(restored, created)

    async def test_missing_task_is_reported(self) -> None:
        with self.assertRaises(NotFoundError):
            await self.context.task_service.get_task("task_missing")

    async def test_database_event_store_and_projection_are_composable(self) -> None:
        database = Database(self.data_dir / "manual")
        database.initialize()
        projection = TaskProjection()
        store = SqliteEventStore(database, projectors=(projection,))
        service = TaskService(store, database, projection)

        created = await service.create_task("Optimize parser")
        with database.connect() as connection:
            projected = projection.get(connection, str(created.id))

        self.assertEqual(projected, created)

    async def test_empty_objective_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            await self.context.task_service.create_task("   ")


if __name__ == "__main__":
    unittest.main()
