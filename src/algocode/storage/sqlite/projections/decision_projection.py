"""Read model for decisions."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import (
    ArtifactRef,
    CandidateId,
    Decision,
    DecisionId,
    DecisionOutcome,
    TaskId,
)


class DecisionProjection:
    """Persist accepted and rejected decisions inside event transactions."""

    def apply(self, connection: sqlite3.Connection, event: EventEnvelope) -> None:
        if event.type is not EventType.DECISION_MADE:
            return
        payload = event.payload
        connection.execute(
            """
            INSERT OR REPLACE INTO decisions(
                id,
                task_id,
                candidate_id,
                outcome,
                reason,
                evidence_refs_json,
                decided_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["decision_id"],
                event.aggregate_id,
                payload["candidate_id"],
                payload["outcome"],
                payload.get("reason", ""),
                json.dumps(payload.get("evidence_refs", []), ensure_ascii=False, sort_keys=True),
                event.timestamp.isoformat(),
            ),
        )

    def get(self, connection: sqlite3.Connection, decision_id: str) -> Decision | None:
        row = connection.execute(
            "SELECT * FROM decisions WHERE id = ?",
            (decision_id,),
        ).fetchone()
        return None if row is None else self._to_decision(row)

    def get_for_candidate(
        self,
        connection: sqlite3.Connection,
        candidate_id: str,
    ) -> Decision | None:
        row = connection.execute(
            """
            SELECT *
            FROM decisions
            WHERE candidate_id = ?
            ORDER BY decided_at DESC
            LIMIT 1
            """,
            (candidate_id,),
        ).fetchone()
        return None if row is None else self._to_decision(row)

    @staticmethod
    def _to_decision(row: sqlite3.Row) -> Decision:
        evidence = json.loads(row["evidence_refs_json"])
        return Decision(
            id=DecisionId(row["id"]),
            task_id=TaskId(row["task_id"]),
            candidate_id=CandidateId(row["candidate_id"]),
            outcome=DecisionOutcome(row["outcome"]),
            reason=row["reason"],
            evidence_refs=[
                ArtifactRef(uri=item["uri"], sha256=item["sha256"]) for item in evidence
            ],
            decided_at=_parse_datetime(row["decided_at"]),
        )


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise TypeError("stored timestamp must be text")
    return datetime.fromisoformat(value)
