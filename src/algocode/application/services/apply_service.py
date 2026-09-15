"""Apply accepted candidates to the user workspace and roll them back."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from algocode.application.services.candidate_service import CandidateService
from algocode.application.services.decision_service import DecisionService
from algocode.application.services.project_service import ProjectService
from algocode.application.services.task_service import TaskService
from algocode.domain.errors import DecisionError
from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import CandidateId, CandidateStatus, DecisionOutcome, TaskId
from algocode.ports import ArtifactStore, EventStore
from algocode.workspace import GitRepository, GitWorkspaceManager


class ApplyService:
    """Apply or roll back accepted candidates with stale checks."""

    def __init__(
        self,
        event_store: EventStore,
        task_service: TaskService,
        project_service: ProjectService,
        candidate_service: CandidateService,
        decision_service: DecisionService,
        artifact_store: ArtifactStore,
        data_dir: str | Path,
    ) -> None:
        self._event_store = event_store
        self._task_service = task_service
        self._project_service = project_service
        self._candidate_service = candidate_service
        self._decision_service = decision_service
        self._artifact_store = artifact_store
        self._data_dir = Path(data_dir)

    async def apply(
        self,
        task_id: TaskId | str,
        candidate_id: CandidateId | str,
    ) -> dict[str, object]:
        task = await self._task_service.get_task(task_id)
        candidate = await self._candidate_service.get(candidate_id)
        if candidate.task_id != task.id:
            raise DecisionError("candidate does not belong to the task")
        decision = await self._decision_service.get_for_candidate(candidate.id)
        if decision is None or decision.outcome is not DecisionOutcome.ACCEPTED:
            raise DecisionError("candidate must be accepted before apply")
        if candidate.status is CandidateStatus.APPLIED:
            raise DecisionError("candidate is already applied")
        project = await self._project_service.get(task.project_id)
        repository = await GitRepository.discover(project.root_path)
        current = await repository.capture_snapshot(repository.root)
        if (
            current.revision != candidate.base_revision.value
            or current.snapshot_hash != candidate.base_snapshot_hash
        ):
            await self._mark_stale(task.id, candidate.id)
            raise DecisionError("candidate is stale; re-verify before apply")
        candidate_snapshot = await repository.capture_snapshot(Path(candidate.workspace_ref))
        patch_ref = await self._artifact_store.put(
            candidate_snapshot.patch,
            kind="candidate-patch",
            mime_type="application/x-git-patch",
            metadata={"task_id": str(task.id), "candidate_id": str(candidate.id)},
        )
        manager = GitWorkspaceManager(repository, self._data_dir)
        workspace = await self._candidate_service.workspace(candidate.id)
        result = await manager.apply(workspace)
        if not result.applied:
            raise DecisionError(result.message or "candidate apply failed")
        applied_snapshot = await repository.capture_snapshot(repository.root)
        seq = await self._next_seq(str(task.id))
        await self._event_store.append(
            str(task.id),
            seq - 1,
            (
                _event(
                    str(task.id),
                    seq,
                    EventType.CANDIDATE_APPLIED,
                    {
                        "candidate_id": str(candidate.id),
                        "workspace_id": workspace.id,
                        "reverse_patch_ref": _artifact_payload(patch_ref),
                        "applied_snapshot_hash": applied_snapshot.snapshot_hash,
                    },
                ),
            ),
        )
        return {
            "candidate_id": str(candidate.id),
            "applied": True,
            "patch_ref": _artifact_payload(patch_ref),
        }

    async def rollback(
        self,
        task_id: TaskId | str,
        candidate_id: CandidateId | str,
    ) -> dict[str, object]:
        task = await self._task_service.get_task(task_id)
        candidate = await self._candidate_service.get(candidate_id)
        if candidate.status is not CandidateStatus.APPLIED:
            raise DecisionError("candidate is not applied")
        project = await self._project_service.get(task.project_id)
        repository = await GitRepository.discover(project.root_path)
        manager = GitWorkspaceManager(repository, self._data_dir)
        workspace = await self._candidate_service.workspace(candidate.id)
        await manager.rollback(workspace)
        seq = await self._next_seq(str(task.id))
        await self._event_store.append(
            str(task.id),
            seq - 1,
            (
                _event(
                    str(task.id),
                    seq,
                    EventType.CANDIDATE_ROLLED_BACK,
                    {"candidate_id": str(candidate.id), "workspace_id": workspace.id},
                ),
            ),
        )
        return {"candidate_id": str(candidate.id), "rolled_back": True}

    async def _mark_stale(self, task_id: TaskId, candidate_id: CandidateId) -> None:
        seq = await self._next_seq(str(task_id))
        await self._event_store.append(
            str(task_id),
            seq - 1,
            (
                _event(
                    str(task_id),
                    seq,
                    EventType.CANDIDATE_REJECTED,
                    {"candidate_id": str(candidate_id), "status": CandidateStatus.STALE.value},
                ),
            ),
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


def _artifact_payload(ref) -> dict[str, str]:
    return {"uri": ref.uri, "sha256": ref.sha256}
