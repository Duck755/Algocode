from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from algocode.domain.errors import ConcurrencyError, EventConflictError
from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import ArtifactRef
from algocode.storage.events import SqliteEventStore
from algocode.storage.sqlite import Database


class EventStoreContractTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temporary_directory.name))
        self.database.initialize()
        self.store = SqliteEventStore(self.database)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def _event(
        event_id: str,
        aggregate_id: str,
        seq: int,
        event_type: EventType,
    ) -> EventEnvelope:
        return EventEnvelope(
            id=event_id,
            aggregate_id=aggregate_id,
            seq=seq,
            type=event_type,
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            payload={"seq": seq},
            artifact_refs=(ArtifactRef(uri="artifact://example", sha256="abc"),),
        )

    async def test_append_and_read_round_trip(self) -> None:
        aggregate_id = "task_1"
        first = self._event("evt_1", aggregate_id, 1, EventType.TASK_CREATED)
        second = self._event("evt_2", aggregate_id, 2, EventType.BASELINE_STARTED)

        await self.store.append(aggregate_id, 0, (first,))
        await self.store.append(aggregate_id, 1, (second,))

        events = await self.store.read(aggregate_id)
        self.assertEqual([event.id for event in events], ["evt_1", "evt_2"])
        self.assertEqual(events[0].artifact_refs[0].uri, "artifact://example")
        self.assertEqual((await self.store.read(aggregate_id, after=1))[0].id, "evt_2")

    async def test_expected_sequence_mismatch_is_rejected(self) -> None:
        aggregate_id = "task_1"
        first = self._event("evt_1", aggregate_id, 1, EventType.TASK_CREATED)

        with self.assertRaises(ConcurrencyError):
            await self.store.append(aggregate_id, 10, (first,))
        self.assertEqual(await self.store.read(aggregate_id), ())

    async def test_non_contiguous_sequence_is_rejected(self) -> None:
        aggregate_id = "task_1"
        event = self._event("evt_1", aggregate_id, 2, EventType.TASK_CREATED)

        with self.assertRaises(EventConflictError):
            await self.store.append(aggregate_id, 0, (event,))
        self.assertEqual(await self.store.read(aggregate_id), ())

    async def test_duplicate_event_id_is_rejected(self) -> None:
        first = self._event("evt_1", "task_1", 1, EventType.TASK_CREATED)
        duplicate = self._event("evt_1", "task_2", 1, EventType.TASK_CREATED)

        await self.store.append("task_1", 0, (first,))
        with self.assertRaises(EventConflictError):
            await self.store.append("task_2", 0, (duplicate,))


if __name__ == "__main__":
    unittest.main()
