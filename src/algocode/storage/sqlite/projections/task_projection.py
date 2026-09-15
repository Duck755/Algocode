"""Read model for optimization tasks."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import ProjectId, Task, TaskId, TaskPhase, TaskStatus


class TaskProjection:
    """Maintain the task read model inside event transactions."""

    def apply(self, connection: sqlite3.Connection, event: EventEnvelope) -> None:
        if event.type is EventType.TASK_CREATED:
            self._insert_task(connection, event)
        elif event.type in {
            EventType.TASK_COMPLETED,
            EventType.TASK_FAILED,
            EventType.TASK_CANCELLED,
        }:
            connection.execute(
                """
                UPDATE tasks
                SET status = ?, current_phase = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    event.payload["status"],
                    event.payload["current_phase"],
                    event.payload.get("completed_at"),
                    event.timestamp.isoformat(),
                    event.aggregate_id,
                ),
            )
        elif event.type is EventType.TASK_PHASE_CHANGED:
            connection.execute(
                """
                UPDATE tasks
                SET status = ?, current_phase = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    event.payload["status"],
                    event.payload["current_phase"],
                    event.timestamp.isoformat(),
                    event.aggregate_id,
                ),
            )
        elif event.type is EventType.BASELINE_CAPTURED:
            connection.execute(
                """
                UPDATE tasks
                SET baseline_id = ?, status = ?, current_phase = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    event.payload["baseline_id"],
                    TaskStatus.READY.value,
                    TaskPhase.ANALYZE.value,
                    event.timestamp.isoformat(),
                    event.aggregate_id,
                ),
            )
        elif event.type is EventType.DECISION_MADE and event.payload.get("outcome") == "accepted":
            connection.execute(
                """
                UPDATE tasks
                SET active_candidate_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    event.payload["candidate_id"],
                    event.timestamp.isoformat(),
                    event.aggregate_id,
                ),
            )
        elif event.type is EventType.BASELINE_FAILED:
            connection.execute(
                """
                UPDATE tasks
                SET status = ?, current_phase = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    TaskStatus.FAILED.value,
                    TaskPhase.BASELINE.value,
                    event.timestamp.isoformat(),
                    event.aggregate_id,
                ),
            )
        elif (
            event.type is EventType.CORRECTNESS_FAILED
            and event.payload.get("target_kind") == "baseline"
        ):
            connection.execute(
                """
                UPDATE tasks
                SET status = ?, current_phase = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    TaskStatus.FAILED.value,
                    TaskPhase.VERIFY.value,
                    event.timestamp.isoformat(),
                    event.aggregate_id,
                ),
            )

    @staticmethod
    def _insert_task(connection: sqlite3.Connection, event: EventEnvelope) -> None:
        payload = event.payload
        connection.execute(
            """
            INSERT INTO tasks(
                id,
                project_id,
                objective,
                status,
                current_phase,
                baseline_id,
                active_candidate_id,
                created_at,
                updated_at,
                completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["task_id"],
                payload["project_id"],
                payload["objective"],
                payload["status"],
                payload["current_phase"],
                payload.get("baseline_id"),
                payload.get("active_candidate_id"),
                payload["created_at"],
                payload["updated_at"],
                payload.get("completed_at"),
            ),
        )

    def get(self, connection: sqlite3.Connection, task_id: str) -> Task | None:
        row = connection.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        return None if row is None else self._to_task(row)

    def list(self, connection: sqlite3.Connection) -> list[Task]:
        rows = connection.execute("SELECT * FROM tasks ORDER BY created_at DESC, id").fetchall()
        return [self._to_task(row) for row in rows]

    @staticmethod
    def _to_task(row: sqlite3.Row) -> Task:
        return Task(
            id=TaskId(row["id"]),
            project_id=ProjectId(row["project_id"]),
            objective=row["objective"],
            status=TaskStatus(row["status"]),
            current_phase=TaskPhase(row["current_phase"]),
            baseline_id=row["baseline_id"],
            active_candidate_id=row["active_candidate_id"],
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
            completed_at=_parse_optional_datetime(row["completed_at"]),
        )


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise TypeError("stored timestamp must be text")
    return datetime.fromisoformat(value)


def _parse_optional_datetime(value: Any) -> datetime | None:
    return None if value is None else _parse_datetime(value)
