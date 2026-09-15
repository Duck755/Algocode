"""Persistent approval grants."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from algocode.approval.types import ApprovalDecision, ApprovalRequest, ApprovalScope
from algocode.security import SecretRedactor
from algocode.storage.sqlite.database import Database


class ApprovalStore:
    def __init__(self, database: Database, redactor: SecretRedactor | None = None) -> None:
        self._database = database
        self._redactor = redactor or SecretRedactor()

    def find(self, request: ApprovalRequest) -> ApprovalDecision | None:
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM approvals
                WHERE approved = 1
                  AND action = ?
                  AND resource = ?
                  AND (
                    (scope = 'task' AND task_id = ?)
                    OR (scope = 'project' AND project_id = ?)
                  )
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (request.action, request.resource, request.task_id, request.project_id),
            ).fetchone()
        if row is None:
            return None
        return ApprovalDecision(
            approved=True,
            scope=ApprovalScope(row["scope"]),
            reason="approval grant reused",
        )

    def save(self, request: ApprovalRequest, decision: ApprovalDecision) -> None:
        if decision.scope not in {ApprovalScope.TASK, ApprovalScope.PROJECT}:
            return
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO approvals(
                    id, task_id, project_id, action, resource, scope, approved, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"approval_{uuid4().hex}",
                    request.task_id,
                    request.project_id,
                    self._redactor.redact_text(request.action),
                    self._redactor.redact_text(request.resource),
                    decision.scope.value,
                    1 if decision.approved else 0,
                    datetime.now(UTC).isoformat(),
                ),
            )
