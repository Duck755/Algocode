"""Read model for optimization experiments."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import (
    CandidateId,
    DecisionOutcome,
    Experiment,
    ExperimentId,
    ExperimentStatus,
    TaskId,
)


class ExperimentProjection:
    """Persist independent experiment aggregates inside event transactions."""

    def apply(self, connection: sqlite3.Connection, event: EventEnvelope) -> None:
        payload = event.payload
        experiment_id = payload.get("experiment_id")
        if not isinstance(experiment_id, str) or not experiment_id:
            return
        if event.type is EventType.EXPERIMENT_CREATED:
            connection.execute(
                """
                INSERT OR REPLACE INTO experiments(
                    id,
                    task_id,
                    baseline_id,
                    candidate_id,
                    spec_hash,
                    input_hash,
                    environment_hash,
                    comparison_key,
                    policy_hash,
                    status,
                    decision,
                    started_at,
                    completed_at,
                    invalidation_reason,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment_id,
                    event.aggregate_id,
                    payload["baseline_id"],
                    payload["candidate_id"],
                    payload.get("spec_hash", ""),
                    payload.get("input_hash", ""),
                    payload.get("environment_hash", ""),
                    payload.get("comparison_key", ""),
                    payload.get("policy_hash", ""),
                    ExperimentStatus.CREATED.value,
                    None,
                    None,
                    None,
                    None,
                    event.timestamp.isoformat(),
                ),
            )
            return
        if event.type is EventType.EXPERIMENT_STARTED:
            connection.execute(
                """
                UPDATE experiments
                SET status = ?, started_at = ?
                WHERE id = ?
                """,
                (
                    ExperimentStatus.RUNNING.value,
                    event.timestamp.isoformat(),
                    experiment_id,
                ),
            )
            return
        if event.type is EventType.EXPERIMENT_COMPLETED:
            decision = payload.get("decision")
            connection.execute(
                """
                UPDATE experiments
                SET status = ?, decision = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    ExperimentStatus.COMPLETED.value,
                    decision if isinstance(decision, str) else None,
                    event.timestamp.isoformat(),
                    experiment_id,
                ),
            )
            return
        if event.type is EventType.EXPERIMENT_FAILED:
            connection.execute(
                """
                UPDATE experiments
                SET status = ?, completed_at = ?, invalidation_reason = ?
                WHERE id = ?
                """,
                (
                    ExperimentStatus.FAILED.value,
                    event.timestamp.isoformat(),
                    str(payload.get("reason", ""))[:2000],
                    experiment_id,
                ),
            )
            return
        if event.type is EventType.EXPERIMENT_INVALIDATED:
            connection.execute(
                """
                UPDATE experiments
                SET status = ?, invalidation_reason = ?
                WHERE id = ?
                """,
                (
                    ExperimentStatus.INVALID.value,
                    str(payload.get("reason", ""))[:2000],
                    experiment_id,
                ),
            )

    def get(self, connection: sqlite3.Connection, experiment_id: str) -> Experiment | None:
        row = connection.execute(
            "SELECT * FROM experiments WHERE id = ?",
            (experiment_id,),
        ).fetchone()
        return None if row is None else self._to_experiment(row)

    def get_for_candidate(
        self,
        connection: sqlite3.Connection,
        candidate_id: str,
    ) -> Experiment | None:
        row = connection.execute(
            """
            SELECT *
            FROM experiments
            WHERE candidate_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (candidate_id,),
        ).fetchone()
        return None if row is None else self._to_experiment(row)

    def list_for_task(
        self,
        connection: sqlite3.Connection,
        task_id: str,
    ) -> list[Experiment]:
        rows = connection.execute(
            """
            SELECT *
            FROM experiments
            WHERE task_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (task_id,),
        ).fetchall()
        return [self._to_experiment(row) for row in rows]

    @staticmethod
    def _to_experiment(row: sqlite3.Row) -> Experiment:
        return Experiment(
            id=ExperimentId(row["id"]),
            task_id=TaskId(row["task_id"]),
            baseline_id=row["baseline_id"],
            candidate_id=CandidateId(row["candidate_id"]),
            spec_hash=row["spec_hash"],
            input_hash=row["input_hash"],
            environment_hash=row["environment_hash"],
            comparison_key=row["comparison_key"],
            policy_hash=row["policy_hash"],
            status=ExperimentStatus(row["status"]),
            decision=(
                DecisionOutcome(row["decision"]) if row["decision"] is not None else None
            ),
            started_at=_parse_optional_datetime(row["started_at"]),
            completed_at=_parse_optional_datetime(row["completed_at"]),
            invalidation_reason=row["invalidation_reason"],
            created_at=_parse_datetime(row["created_at"]),
        )


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise TypeError("stored timestamp must be text")
    return datetime.fromisoformat(value)


def _parse_optional_datetime(value: Any) -> datetime | None:
    return None if value is None else _parse_datetime(value)
