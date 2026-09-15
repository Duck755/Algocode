"""Durable event store port."""

from collections.abc import Sequence
from typing import Protocol

from algocode.domain.events import EventEnvelope


class EventStore(Protocol):
    """Append with optimistic concurrency and read ordered events.

    ``expected_seq`` is the last stored sequence. An empty aggregate uses 0,
    so the first persisted event has sequence 1.
    """

    async def append(
        self,
        aggregate_id: str,
        expected_seq: int,
        events: Sequence[EventEnvelope],
    ) -> None: ...

    async def read(self, aggregate_id: str, after: int = -1) -> Sequence[EventEnvelope]: ...
