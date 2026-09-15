"""Read model for correctness runs."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import (
    ArtifactRef,
    CorrectnessRun,
    CorrectnessStatus,
    FailureKind,
    TaskId,
)


class CorrectnessProjection:
    """Persist correctness run state inside event transactions."""

    def apply(self, connection: sqlite3.Connection, event: EventEnvelope) -> None:
        if event.type is EventType.CORRECTNESS_STARTED:
            payload = event.payload
            connection.execute(
                """
                INSERT INTO correctness_runs(
                    id,
                    task_id,
                    target_kind,
                    target_id,
                    workspace_ref,
                    spec_hash,
                    status,
                    spec_ref_json,
                    result_ref_json,
                    failure_kind,
                    started_at,
                    completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["result_id"],
                    event.aggregate_id,
                    payload["target_kind"],
                    payload["target_id"],
                    payload["workspace_ref"],
                    payload["spec_hash"],
                    CorrectnessStatus.RUNNING.value,
                    _encode_ref(payload["spec_ref"]),
                    None,
                    None,
                    event.timestamp.isoformat(),
                    None,
                ),
            )
            return
        if event.type not in {EventType.CORRECTNESS_PASSED, EventType.CORRECTNESS_FAILED}:
            return
        payload = event.payload
        connection.execute(
            """
            UPDATE correctness_runs
            SET status = ?, result_ref_json = ?, failure_kind = ?, completed_at = ?
            WHERE id = ?
            """,
            (
                payload["status"],
                _encode_ref(payload.get("result_ref")),
                payload.get("failure_kind"),
                event.timestamp.isoformat(),
                payload["result_id"],
            ),
        )

    def get(self, connection: sqlite3.Connection, result_id: str) -> CorrectnessRun | None:
        row = connection.execute(
            "SELECT * FROM correctness_runs WHERE id = ?",
            (result_id,),
        ).fetchone()
        return None if row is None else self._to_run(row)

    def list_for_task(
        self,
        connection: sqlite3.Connection,
        task_id: str,
    ) -> list[CorrectnessRun]:
        rows = connection.execute(
            """
            SELECT *
            FROM correctness_runs
            WHERE task_id = ?
            ORDER BY started_at DESC, id
            """,
            (task_id,),
        ).fetchall()
        return [self._to_run(row) for row in rows]

    @staticmethod
    def _to_run(row: sqlite3.Row) -> CorrectnessRun:
        return CorrectnessRun(
            id=row["id"],
            task_id=TaskId(row["task_id"]),
            target_kind=row["target_kind"],
            target_id=row["target_id"],
            workspace_ref=row["workspace_ref"],
            spec_hash=row["spec_hash"],
            status=CorrectnessStatus(row["status"]),
            spec_ref=_decode_ref(row["spec_ref_json"]),
            result_ref=_decode_optional_ref(row["result_ref_json"]),
            failure_kind=(
                FailureKind(row["failure_kind"]) if row["failure_kind"] is not None else None
            ),
            started_at=_parse_datetime(row["started_at"]),
            completed_at=_parse_optional_datetime(row["completed_at"]),
        )


def _encode_ref(value: Any) -> str:
    payload = value if isinstance(value, dict) else {"uri": value.uri, "sha256": value.sha256}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _encode_optional_ref(value: Any) -> str | None:
    return None if value is None else _encode_ref(value)


def _decode_ref(value: Any) -> ArtifactRef:
    if not isinstance(value, str):
        raise TypeError("stored artifact reference must be text")
    payload = json.loads(value)
    return ArtifactRef(uri=payload["uri"], sha256=payload["sha256"])


def _decode_optional_ref(value: Any) -> ArtifactRef | None:
    return None if value is None else _decode_ref(value)


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise TypeError("stored timestamp must be text")
    return datetime.fromisoformat(value)


def _parse_optional_datetime(value: Any) -> datetime | None:
    return None if value is None else _parse_datetime(value)
