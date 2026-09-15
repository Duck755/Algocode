"""SQLite-backed durable event store."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime

from algocode.domain.errors import ConcurrencyError, EventConflictError, InvariantViolation
from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import ArtifactRef
from algocode.security import SecretRedactor
from algocode.storage.sqlite.database import Database
from algocode.storage.sqlite.projections import Projector


class SqliteEventStore:
    """Persist events and update projections in one transaction."""

    def __init__(
        self,
        database: Database,
        projectors: Sequence[Projector] = (),
        redactor: SecretRedactor | None = None,
    ) -> None:
        self._database = database
        self._projectors = tuple(projectors)
        self._redactor = redactor or SecretRedactor()

    async def append(
        self,
        aggregate_id: str,
        expected_seq: int,
        events: Sequence[EventEnvelope],
    ) -> None:
        pending = tuple(events)
        if not pending:
            return
        with self._database.transaction(immediate=True) as connection:
            current_seq = self._current_seq(connection, aggregate_id)
            if current_seq != expected_seq:
                raise ConcurrencyError(
                    f"expected sequence {expected_seq} for {aggregate_id}, found {current_seq}"
                )
            for offset, event in enumerate(pending, start=1):
                safe_event = replace(
                    event,
                    payload=self._redactor.redact_value(event.payload),
                )
                if event.aggregate_id != aggregate_id:
                    raise InvariantViolation(
                        f"event {event.id} belongs to {event.aggregate_id}, not {aggregate_id}"
                    )
                if event.seq != expected_seq + offset:
                    raise EventConflictError(
                        f"event {event.id} has sequence {event.seq}; "
                        f"expected {expected_seq + offset}"
                    )
                try:
                    connection.execute(
                        """
                        INSERT INTO event_log(
                            id,
                            aggregate_id,
                            seq,
                            type,
                            schema_version,
                            timestamp,
                            payload_json,
                            artifact_refs_json
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event.id,
                            event.aggregate_id,
                            event.seq,
                            event.type.value,
                            event.schema_version,
                            event.timestamp.isoformat(),
                            json.dumps(safe_event.payload, ensure_ascii=False, sort_keys=True),
                            json.dumps(
                                [
                                    {"uri": ref.uri, "sha256": ref.sha256}
                                    for ref in event.artifact_refs
                                ],
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise EventConflictError(f"event {event.id} already exists") from exc
                for projector in self._projectors:
                    projector.apply(connection, safe_event)

    async def read(self, aggregate_id: str, after: int = -1) -> Sequence[EventEnvelope]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM event_log
                WHERE aggregate_id = ? AND seq > ?
                ORDER BY seq
                """,
                (aggregate_id, after),
            ).fetchall()
        return tuple(_from_row(row) for row in rows)

    @staticmethod
    def _current_seq(connection: sqlite3.Connection, aggregate_id: str) -> int:
        row = connection.execute(
            "SELECT COALESCE(MAX(seq), 0) AS current_seq FROM event_log WHERE aggregate_id = ?",
            (aggregate_id,),
        ).fetchone()
        return int(row["current_seq"])


def _from_row(row: sqlite3.Row) -> EventEnvelope:
    payload = json.loads(row["payload_json"])
    artifacts = json.loads(row["artifact_refs_json"])
    return EventEnvelope(
        id=row["id"],
        aggregate_id=row["aggregate_id"],
        seq=int(row["seq"]),
        type=EventType(row["type"]),
        schema_version=int(row["schema_version"]),
        timestamp=datetime.fromisoformat(row["timestamp"]),
        payload=payload,
        artifact_refs=tuple(
            ArtifactRef(uri=item["uri"], sha256=item["sha256"]) for item in artifacts
        ),
    )
