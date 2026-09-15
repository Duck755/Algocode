"""Read model for immutable baselines."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import ArtifactRef, Baseline, GitRevision, TaskId


class BaselineProjection:
    """Persist captured baselines inside event transactions."""

    def apply(self, connection: sqlite3.Connection, event: EventEnvelope) -> None:
        if (
            event.type is EventType.BENCHMARK_SAMPLES_CAPTURED
            and event.payload.get("target_kind") == "baseline"
        ):
            connection.execute(
                """
                UPDATE baselines
                SET benchmark_result_ref_json = ?
                WHERE id = ?
                """,
                (
                    _encode_optional_ref(event.payload.get("result_ref")),
                    event.payload["target_id"],
                ),
            )
            return
        if (
            event.type is EventType.CORRECTNESS_PASSED
            and event.payload.get("target_kind") == "baseline"
        ):
            connection.execute(
                """
                UPDATE baselines
                SET correctness_result_ref_json = ?
                WHERE id = ?
                """,
                (
                    _encode_optional_ref(event.payload.get("result_ref")),
                    event.payload["target_id"],
                ),
            )
            return
        if event.type is not EventType.BASELINE_CAPTURED:
            return
        payload = event.payload
        connection.execute(
            """
            INSERT INTO baselines(
                id,
                task_id,
                revision,
                snapshot_hash,
                environment_hash,
                build_result_ref_json,
                correctness_result_ref_json,
                benchmark_result_ref_json,
                workspace_ref,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["baseline_id"],
                event.aggregate_id,
                payload["revision"],
                payload["snapshot_hash"],
                payload["environment_hash"],
                _encode_optional_ref(payload.get("build_result_ref")),
                _encode_optional_ref(payload.get("correctness_result_ref")),
                _encode_optional_ref(payload.get("benchmark_result_ref")),
                payload.get("workspace_ref"),
                payload["created_at"],
            ),
        )

    def get(self, connection: sqlite3.Connection, baseline_id: str) -> Baseline | None:
        row = connection.execute(
            "SELECT * FROM baselines WHERE id = ?",
            (baseline_id,),
        ).fetchone()
        return None if row is None else self._to_baseline(row)

    def get_for_task(self, connection: sqlite3.Connection, task_id: str) -> Baseline | None:
        row = connection.execute(
            """
            SELECT *
            FROM baselines
            WHERE task_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (task_id,),
        ).fetchone()
        return None if row is None else self._to_baseline(row)

    @staticmethod
    def _to_baseline(row: sqlite3.Row) -> Baseline:
        return Baseline(
            id=row["id"],
            task_id=TaskId(row["task_id"]),
            revision=GitRevision(row["revision"]),
            snapshot_hash=row["snapshot_hash"],
            environment_hash=row["environment_hash"],
            build_result_ref=_decode_optional_ref(row["build_result_ref_json"]),
            correctness_result_ref=_decode_optional_ref(row["correctness_result_ref_json"]),
            benchmark_result_ref=_decode_optional_ref(row["benchmark_result_ref_json"]),
            workspace_ref=row["workspace_ref"],
            created_at=_parse_datetime(row["created_at"]),
        )


def _encode_optional_ref(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _decode_optional_ref(value: Any) -> ArtifactRef | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("stored artifact reference must be text")
    payload = json.loads(value)
    return ArtifactRef(uri=payload["uri"], sha256=payload["sha256"])


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise TypeError("stored timestamp must be text")
    return datetime.fromisoformat(value)
