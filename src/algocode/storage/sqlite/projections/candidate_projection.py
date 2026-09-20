"""Read model for candidates."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import Candidate, CandidateId, CandidateStatus, GitRevision, TaskId


class CandidateProjection:
    """Maintain candidate lifecycle state inside event transactions."""

    def apply(self, connection: sqlite3.Connection, event: EventEnvelope) -> None:
        if event.type is EventType.CANDIDATE_CREATED:
            payload = event.payload
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
                    payload["candidate_id"],
                    event.aggregate_id,
                    payload["base_revision"],
                    payload["base_snapshot_hash"],
                    payload["workspace_ref"],
                    payload["status"],
                    payload.get("patch_hash"),
                    payload["created_at"],
                    payload.get("frozen_at"),
                    payload.get("parent_candidate_id"),
                    payload.get("fork_snapshot_hash"),
                    payload.get("apply_base_revision"),
                    payload.get("apply_base_snapshot_hash"),
                ),
            )
            return
        if event.type is EventType.CANDIDATE_FROZEN:
            connection.execute(
                """
                UPDATE candidates
                SET status = ?, patch_hash = ?, frozen_at = ?
                WHERE id = ?
                """,
                (
                    CandidateStatus.FROZEN.value,
                    event.payload["patch_hash"],
                    event.timestamp.isoformat(),
                    event.payload["candidate_id"],
                ),
            )
            return
        if event.type is EventType.CANDIDATE_REOPENED:
            connection.execute(
                """
                UPDATE candidates
                SET status = ?, frozen_at = NULL
                WHERE id = ?
                """,
                (
                    CandidateStatus.EDITING.value,
                    event.payload["candidate_id"],
                ),
            )
            return
        if (
            event.type is EventType.CORRECTNESS_PASSED
            and event.payload.get("target_kind") == "candidate"
            and event.payload.get("record_candidate_status", True)
        ):
            self._set_status(connection, str(event.payload["target_id"]), CandidateStatus.VERIFIED)
            return
        if (
            event.type is EventType.CORRECTNESS_FAILED
            and event.payload.get("target_kind") == "candidate"
            and event.payload.get("record_candidate_status", True)
        ):
            self._set_status(connection, str(event.payload["target_id"]), CandidateStatus.REJECTED)
            return
        if event.type is EventType.CANDIDATE_SELECTED:
            candidate_id = str(
                event.payload.get("candidate_id", event.payload.get("target_id", ""))
            )
            if candidate_id:
                self._set_status(connection, candidate_id, CandidateStatus.SELECTED)
            return
        if event.type is EventType.DECISION_MADE:
            candidate_id = str(
                event.payload.get("candidate_id", event.payload.get("target_id", ""))
            )
            if not candidate_id:
                return
            outcome = event.payload.get("outcome")
            if outcome == "accepted":
                self._set_status(connection, candidate_id, CandidateStatus.SELECTED)
            elif outcome == "rejected":
                self._set_status(connection, candidate_id, CandidateStatus.REJECTED)
            elif outcome == "inconclusive":
                self._set_status(connection, candidate_id, CandidateStatus.INCONCLUSIVE)
            return
        if event.type is EventType.CANDIDATE_APPLIED:
            self._set_status(
                connection, str(event.payload["candidate_id"]), CandidateStatus.APPLIED
            )
            return
        if event.type is EventType.CANDIDATE_ROLLED_BACK:
            self._set_status(
                connection,
                str(event.payload["candidate_id"]),
                CandidateStatus.ROLLED_BACK,
            )
            return
        if event.type is EventType.CANDIDATE_REJECTED:
            status = (
                CandidateStatus.STALE
                if event.payload.get("status") == CandidateStatus.STALE.value
                else CandidateStatus.REJECTED
            )
            self._set_status(connection, str(event.payload["candidate_id"]), status)

    def get(self, connection: sqlite3.Connection, candidate_id: str) -> Candidate | None:
        row = connection.execute(
            "SELECT * FROM candidates WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        return None if row is None else self._to_candidate(row)

    def list_for_task(
        self,
        connection: sqlite3.Connection,
        task_id: str,
    ) -> list[Candidate]:
        rows = connection.execute(
            """
            SELECT *
            FROM candidates
            WHERE task_id = ?
            ORDER BY created_at DESC, id
            """,
            (task_id,),
        ).fetchall()
        return [self._to_candidate(row) for row in rows]

    @staticmethod
    def _set_status(
        connection: sqlite3.Connection,
        candidate_id: str,
        status: CandidateStatus,
    ) -> None:
        connection.execute(
            "UPDATE candidates SET status = ? WHERE id = ?",
            (status.value, candidate_id),
        )

    @staticmethod
    def _to_candidate(row: sqlite3.Row) -> Candidate:
        return Candidate(
            id=CandidateId(row["id"]),
            task_id=TaskId(row["task_id"]),
            base_revision=GitRevision(row["base_revision"]),
            base_snapshot_hash=row["base_snapshot_hash"],
            workspace_ref=row["workspace_ref"],
            status=CandidateStatus(row["status"]),
            patch_hash=row["patch_hash"],
            created_at=_parse_datetime(row["created_at"]),
            frozen_at=_parse_optional_datetime(row["frozen_at"]),
            parent_candidate_id=(
                CandidateId(row["parent_candidate_id"]) if row["parent_candidate_id"] else None
            ),
            fork_snapshot_hash=row["fork_snapshot_hash"],
            apply_base_revision=(
                GitRevision(row["apply_base_revision"]) if row["apply_base_revision"] else None
            ),
            apply_base_snapshot_hash=row["apply_base_snapshot_hash"],
        )


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise TypeError("stored timestamp must be text")
    return datetime.fromisoformat(value)


def _parse_optional_datetime(value: Any) -> datetime | None:
    return None if value is None else _parse_datetime(value)
