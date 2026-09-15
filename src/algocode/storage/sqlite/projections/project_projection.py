"""Read model for registered projects."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import Language, Project, ProjectId


class ProjectProjection:
    """Maintain the project registry inside event transactions."""

    def apply(self, connection: sqlite3.Connection, event: EventEnvelope) -> None:
        if event.type is not EventType.PROJECT_REGISTERED:
            return
        payload = event.payload
        connection.execute(
            """
            INSERT INTO projects(
                id,
                root_path,
                name,
                language,
                git_revision,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                root_path = excluded.root_path,
                name = excluded.name,
                language = excluded.language,
                git_revision = excluded.git_revision,
                updated_at = excluded.updated_at
            """,
            (
                payload["project_id"],
                payload["root_path"],
                payload["name"],
                payload["language"],
                payload["git_revision"],
                payload["created_at"],
                payload["updated_at"],
            ),
        )

    def get(self, connection: sqlite3.Connection, project_id: str) -> Project | None:
        row = connection.execute(
            "SELECT * FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
        return None if row is None else self._to_project(row)

    def get_by_root(self, connection: sqlite3.Connection, root_path: str) -> Project | None:
        row = connection.execute(
            "SELECT * FROM projects WHERE root_path = ?",
            (root_path,),
        ).fetchone()
        return None if row is None else self._to_project(row)

    def list(self, connection: sqlite3.Connection) -> list[Project]:
        rows = connection.execute("SELECT * FROM projects ORDER BY updated_at DESC, id").fetchall()
        return [self._to_project(row) for row in rows]

    @staticmethod
    def _to_project(row: sqlite3.Row) -> Project:
        return Project(
            id=ProjectId(row["id"]),
            root_path=row["root_path"],
            name=row["name"],
            language=Language(row["language"]),
            git_revision=row["git_revision"],
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise TypeError("stored timestamp must be text")
    return datetime.fromisoformat(value)
