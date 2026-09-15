"""Per-task durable run lock."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from algocode.domain.errors import ResourceBusyError
from algocode.storage.sqlite.database import Database


class TaskRunLock:
    def __init__(
        self,
        database: Database,
        task_id: str,
        *,
        ttl_seconds: int = 3600,
    ) -> None:
        self._database = database
        self.task_id = task_id
        self.ttl_seconds = ttl_seconds
        self.run_id = f"run_{uuid4().hex}"
        self._acquired = False

    async def __aenter__(self) -> TaskRunLock:
        now = datetime.now(UTC)
        expires = now + timedelta(seconds=self.ttl_seconds)
        with self._database.transaction(immediate=True) as connection:
            row = connection.execute(
                "SELECT run_id, expires_at FROM task_run_locks WHERE task_id = ?",
                (self.task_id,),
            ).fetchone()
            if row is not None:
                if datetime.fromisoformat(row["expires_at"]) > now:
                    raise ResourceBusyError(
                        f"task {self.task_id} is already running as {row['run_id']}"
                    )
                connection.execute(
                    "DELETE FROM task_run_locks WHERE task_id = ?",
                    (self.task_id,),
                )
            connection.execute(
                """
                INSERT INTO task_run_locks(task_id, run_id, acquired_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (self.task_id, self.run_id, now.isoformat(), expires.isoformat()),
            )
        self._acquired = True
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        if not self._acquired:
            return
        with self._database.transaction(immediate=True) as connection:
            connection.execute(
                "DELETE FROM task_run_locks WHERE task_id = ? AND run_id = ?",
                (self.task_id, self.run_id),
            )
        self._acquired = False
