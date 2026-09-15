"""Application service for task lifecycle operations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from algocode.domain.errors import NotFoundError
from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import ProjectId, Task, TaskId, new_project_id, new_task_id
from algocode.ports import EventStore
from algocode.storage.sqlite.database import Database
from algocode.storage.sqlite.projections.task_projection import TaskProjection


class TaskService:
    """Create tasks and restore their current state from the read model."""

    def __init__(
        self,
        event_store: EventStore,
        database: Database,
        task_projection: TaskProjection,
    ) -> None:
        self._event_store = event_store
        self._database = database
        self._task_projection = task_projection

    async def create_task(
        self,
        objective: str,
        project_id: ProjectId | str | None = None,
    ) -> Task:
        normalized_objective = objective.strip()
        if not normalized_objective:
            raise ValueError("task objective must not be empty")

        now = datetime.now(UTC)
        task = Task(
            id=new_task_id(),
            project_id=ProjectId(project_id) if project_id is not None else new_project_id(),
            objective=normalized_objective,
            created_at=now,
            updated_at=now,
        )
        event = EventEnvelope(
            id=f"evt_{uuid4().hex}",
            aggregate_id=str(task.id),
            seq=1,
            type=EventType.TASK_CREATED,
            timestamp=now,
            payload={
                "task_id": str(task.id),
                "project_id": str(task.project_id),
                "objective": task.objective,
                "status": task.status.value,
                "current_phase": task.current_phase.value,
                "baseline_id": task.baseline_id,
                "active_candidate_id": task.active_candidate_id,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
                "completed_at": None,
            },
        )
        await self._event_store.append(str(task.id), 0, (event,))
        return task

    async def list_tasks(self) -> list[Task]:
        with self._database.connect() as connection:
            return self._task_projection.list(connection)

    async def get_task(self, task_id: TaskId | str) -> Task:
        with self._database.connect() as connection:
            task = self._task_projection.get(connection, str(task_id))
        if task is None:
            raise NotFoundError(f"task {task_id} was not found")
        return task
