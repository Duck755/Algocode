"""Read model for benchmark runs and samples."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import ArtifactRef, BenchmarkRun, BenchmarkStatus, TaskId


class BenchmarkProjection:
    """Persist benchmark samples and comparisons inside event transactions."""

    def apply(self, connection: sqlite3.Connection, event: EventEnvelope) -> None:
        if event.type is EventType.EXPERIMENT_CREATED:
            payload = event.payload
            connection.execute(
                """
                INSERT INTO benchmark_runs(
                    id,
                    task_id,
                    target_kind,
                    target_id,
                    workspace_ref,
                    spec_hash,
                    input_hash,
                    environment_hash,
                    comparison_key,
                    status,
                    result_ref_json,
                    comparison_ref_json,
                    correctness_result_id,
                    started_at,
                    completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["run_id"],
                    event.aggregate_id,
                    payload["target_kind"],
                    payload["target_id"],
                    payload["workspace_ref"],
                    payload["spec_hash"],
                    payload["input_hash"],
                    payload["environment_hash"],
                    payload["comparison_key"],
                    BenchmarkStatus.RUNNING.value,
                    None,
                    None,
                    payload.get("correctness_result_id"),
                    event.timestamp.isoformat(),
                    None,
                ),
            )
            return
        if event.type is EventType.BENCHMARK_SAMPLES_CAPTURED:
            payload = event.payload
            connection.execute(
                """
                UPDATE benchmark_runs
                SET result_ref_json = ?, status = ?
                WHERE id = ?
                """,
                (
                    _encode_ref(payload["result_ref"]),
                    BenchmarkStatus.COMPLETED.value,
                    payload["run_id"],
                ),
            )
            for sample in payload["samples"]:
                sample_id = (
                    f"{payload['run_id']}:{sample['target_kind']}:"
                    f"{sample['phase']}:{sample['index']}:{sample.get('input_id', '')}"
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO benchmark_samples(
                        id,
                        benchmark_run_id,
                        target_kind,
                        target_id,
                        phase,
                        sample_index,
                        input_id,
                        metric,
                        value,
                        valid,
                        message
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sample_id,
                        payload["run_id"],
                        sample["target_kind"],
                        sample["target_id"],
                        sample["phase"],
                        sample["index"],
                        sample.get("input_id", ""),
                        sample["metric"],
                        sample["value"],
                        1 if sample["valid"] else 0,
                        sample["message"],
                    ),
                )
            return
        if event.type is EventType.COMPARISON_PRODUCED:
            payload = event.payload
            connection.execute(
                """
                UPDATE benchmark_runs
                SET comparison_ref_json = ?
                WHERE id = ?
                """,
                (_encode_ref(payload["comparison_ref"]), payload["run_id"]),
            )
            return
        if event.type in {EventType.EXPERIMENT_COMPLETED, EventType.EXPERIMENT_FAILED}:
            payload = event.payload
            status = (
                BenchmarkStatus.COMPLETED.value
                if event.type is EventType.EXPERIMENT_COMPLETED
                else BenchmarkStatus.FAILED.value
            )
            connection.execute(
                """
                UPDATE benchmark_runs
                SET status = ?, completed_at = ?
                WHERE id = ?
                """,
                (status, event.timestamp.isoformat(), payload["run_id"]),
            )

    def get(self, connection: sqlite3.Connection, run_id: str) -> BenchmarkRun | None:
        row = connection.execute(
            "SELECT * FROM benchmark_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        return None if row is None else self._to_run(row)

    def list_all(self, connection: sqlite3.Connection) -> list[BenchmarkRun]:
        rows = connection.execute(
            "SELECT * FROM benchmark_runs ORDER BY started_at DESC, id"
        ).fetchall()
        return [self._to_run(row) for row in rows]

    def list_for_task(
        self,
        connection: sqlite3.Connection,
        task_id: str,
    ) -> list[BenchmarkRun]:
        rows = connection.execute(
            """
            SELECT *
            FROM benchmark_runs
            WHERE task_id = ?
            ORDER BY started_at DESC, id
            """,
            (task_id,),
        ).fetchall()
        return [self._to_run(row) for row in rows]

    @staticmethod
    def _to_run(row: sqlite3.Row) -> BenchmarkRun:
        return BenchmarkRun(
            id=row["id"],
            task_id=TaskId(row["task_id"]),
            target_kind=row["target_kind"],
            target_id=row["target_id"],
            workspace_ref=row["workspace_ref"],
            spec_hash=row["spec_hash"],
            input_hash=row["input_hash"],
            environment_hash=row["environment_hash"],
            comparison_key=row["comparison_key"],
            status=BenchmarkStatus(row["status"]),
            result_ref=_decode_optional_ref(row["result_ref_json"]),
            comparison_ref=_decode_optional_ref(row["comparison_ref_json"]),
            correctness_result_id=row["correctness_result_id"],
            started_at=_parse_datetime(row["started_at"]),
            completed_at=_parse_optional_datetime(row["completed_at"]),
        )


def _encode_ref(value: Any) -> str:
    if isinstance(value, dict):
        payload = value
    else:
        payload = {"uri": value.uri, "sha256": value.sha256}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


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


def _parse_optional_datetime(value: Any) -> datetime | None:
    return None if value is None else _parse_datetime(value)
