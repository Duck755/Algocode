"""Candidate workspace lifecycle service."""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from algocode.application.services.baseline_service import BaselineService
from algocode.application.services.project_service import ProjectService
from algocode.application.services.task_service import TaskService
from algocode.domain.errors import NotFoundError
from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import (
    Candidate,
    CandidateId,
    CandidateStatus,
    GitRevision,
    TaskId,
    new_candidate_id,
)
from algocode.ports import EventStore
from algocode.storage.sqlite.database import Database
from algocode.storage.sqlite.projections.candidate_projection import CandidateProjection
from algocode.workspace import GitRepository, GitWorkspaceManager, Workspace, WorkspaceKind


class CandidateService:
    """Create, freeze, and load isolated candidate workspaces."""

    def __init__(
        self,
        event_store: EventStore,
        database: Database,
        task_service: TaskService,
        project_service: ProjectService,
        baseline_service: BaselineService,
        candidate_projection: CandidateProjection,
        data_dir: str | Path,
    ) -> None:
        self._event_store = event_store
        self._database = database
        self._task_service = task_service
        self._project_service = project_service
        self._baseline_service = baseline_service
        self._candidate_projection = candidate_projection
        self._data_dir = Path(data_dir)

    async def create(
        self,
        task_id: TaskId | str,
        base_revision: str | None = None,
        source_workspace: str | Path | None = None,
        parent_candidate_id: str | None = None,
    ) -> Candidate:
        task = await self._task_service.get_task(task_id)
        baseline = await self._baseline_service.get_for_task(task.id)
        if baseline is None:
            raise NotFoundError("baseline must exist before creating a candidate")
        revision = base_revision or baseline.revision.value
        project = await self._project_service.get(task.project_id)
        repository = await GitRepository.discover(project.root_path)
        manager = GitWorkspaceManager(repository, self._data_dir)
        workspace = await manager.create_candidate(
            str(task.id),
            revision,
            source_workspace=Path(source_workspace) if source_workspace is not None else None,
        )
        candidate = Candidate(
            id=new_candidate_id(),
            task_id=task.id,
            base_revision=GitRevision(revision),
            base_snapshot_hash=workspace.base_snapshot_hash,
            workspace_ref=str(workspace.path),
            parent_candidate_id=(CandidateId(parent_candidate_id) if parent_candidate_id else None),
            fork_snapshot_hash=workspace.base_snapshot_hash,
            apply_base_revision=GitRevision(revision),
            apply_base_snapshot_hash=(
                baseline.snapshot_hash
                if source_workspace is not None
                else workspace.base_snapshot_hash
            ),
        )
        seq = await self._next_seq(str(task.id))
        await self._event_store.append(
            str(task.id),
            seq - 1,
            (
                _event(
                    str(task.id),
                    seq,
                    EventType.CANDIDATE_CREATED,
                    {
                        "candidate_id": str(candidate.id),
                        "base_revision": candidate.base_revision.value,
                        "base_snapshot_hash": candidate.base_snapshot_hash,
                        "workspace_ref": candidate.workspace_ref,
                        "status": candidate.status.value,
                        "created_at": candidate.created_at.isoformat(),
                        "parent_candidate_id": (
                            str(candidate.parent_candidate_id)
                            if candidate.parent_candidate_id is not None
                            else None
                        ),
                        "fork_snapshot_hash": candidate.fork_snapshot_hash,
                        "apply_base_revision": (
                            candidate.apply_base_revision.value
                            if candidate.apply_base_revision is not None
                            else None
                        ),
                        "apply_base_snapshot_hash": candidate.apply_base_snapshot_hash,
                    },
                ),
            ),
        )
        return await self.get(candidate.id)

    async def freeze(self, candidate_id: CandidateId | str) -> Candidate:
        candidate = await self.get(candidate_id)
        repository = await GitRepository.discover(candidate.workspace_ref)
        snapshot = await repository.capture_snapshot(Path(candidate.workspace_ref))
        patch_hash = hashlib.sha256(snapshot.patch).hexdigest()
        seq = await self._next_seq(str(candidate.task_id))
        await self._event_store.append(
            str(candidate.task_id),
            seq - 1,
            (
                _event(
                    str(candidate.task_id),
                    seq,
                    EventType.CANDIDATE_FROZEN,
                    {"candidate_id": str(candidate.id), "patch_hash": patch_hash},
                ),
            ),
        )
        return await self.get(candidate.id)

    async def reopen(self, candidate_id: CandidateId | str) -> Candidate:
        """Return a previously decided candidate to the editable lifecycle state."""

        candidate = await self.get(candidate_id)
        if candidate.status in {CandidateStatus.GENERATED, CandidateStatus.EDITING}:
            return candidate
        if candidate.status not in {
            CandidateStatus.REJECTED,
            CandidateStatus.INCONCLUSIVE,
        }:
            raise ValueError(
                f"candidate status {candidate.status.value} cannot be reopened"
            )
        seq = await self._next_seq(str(candidate.task_id))
        await self._event_store.append(
            str(candidate.task_id),
            seq - 1,
            (
                _event(
                    str(candidate.task_id),
                    seq,
                    EventType.CANDIDATE_REOPENED,
                    {"candidate_id": str(candidate.id), "status": CandidateStatus.EDITING.value},
                ),
            ),
        )
        return await self.get(candidate.id)

    async def get(self, candidate_id: CandidateId | str) -> Candidate:
        with self._database.connect() as connection:
            candidate = self._candidate_projection.get(connection, str(candidate_id))
        if candidate is None:
            raise NotFoundError(f"candidate {candidate_id} was not found")
        return candidate

    async def list_for_task(self, task_id: TaskId | str) -> list[Candidate]:
        with self._database.connect() as connection:
            return self._candidate_projection.list_for_task(connection, str(task_id))

    async def workspace(self, candidate_id: CandidateId | str) -> Workspace:
        candidate = await self.get(candidate_id)
        return Workspace(
            id=str(candidate.id),
            kind=WorkspaceKind.CANDIDATE,
            path=Path(candidate.workspace_ref),
            base_revision=candidate.base_revision,
            base_snapshot_hash=candidate.base_snapshot_hash,
        )

    async def _next_seq(self, aggregate_id: str) -> int:
        events = await self._event_store.read(aggregate_id)
        return events[-1].seq + 1 if events else 1


def _event(
    aggregate_id: str,
    seq: int,
    event_type: EventType,
    payload: dict[str, object],
) -> EventEnvelope:
    return EventEnvelope(
        id=f"evt_{uuid4().hex}",
        aggregate_id=aggregate_id,
        seq=seq,
        type=event_type,
        payload=payload,
    )
