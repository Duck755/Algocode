"""Independent experiment aggregate lifecycle service."""

from __future__ import annotations

from uuid import uuid4

from algocode.domain.errors import NotFoundError
from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import (
    DecisionOutcome,
    Experiment,
    ExperimentId,
    TaskId,
    new_experiment_id,
)
from algocode.ports import EventStore
from algocode.storage.sqlite.database import Database
from algocode.storage.sqlite.projections.experiment_projection import ExperimentProjection


class ExperimentService:
    """Create, run, and complete search experiments."""

    def __init__(
        self,
        event_store: EventStore,
        database: Database,
        experiment_projection: ExperimentProjection,
    ) -> None:
        self._event_store = event_store
        self._database = database
        self._experiment_projection = experiment_projection

    async def create(
        self,
        task_id: TaskId | str,
        *,
        candidate_id: str,
        baseline_id: str,
        spec_hash: str,
        input_hash: str,
        environment_hash: str,
        comparison_key: str,
        policy_hash: str,
    ) -> Experiment:
        experiment_id = new_experiment_id()
        seq = await self._next_seq(str(task_id))
        await self._event_store.append(
            str(task_id),
            seq - 1,
            (
                _event(
                    str(task_id),
                    seq,
                    EventType.EXPERIMENT_CREATED,
                    {
                        "experiment_id": str(experiment_id),
                        "baseline_id": baseline_id,
                        "candidate_id": candidate_id,
                        "spec_hash": spec_hash,
                        "input_hash": input_hash,
                        "environment_hash": environment_hash,
                        "comparison_key": comparison_key,
                        "policy_hash": policy_hash,
                    },
                ),
            ),
        )
        return await self.get(experiment_id)

    async def start(self, experiment_id: ExperimentId | str) -> Experiment:
        experiment = await self.get(experiment_id)
        seq = await self._next_seq(str(experiment.task_id))
        await self._event_store.append(
            str(experiment.task_id),
            seq - 1,
            (
                _event(
                    str(experiment.task_id),
                    seq,
                    EventType.EXPERIMENT_STARTED,
                    {"experiment_id": str(experiment.id)},
                ),
            ),
        )
        return await self.get(experiment.id)

    async def complete(
        self,
        experiment_id: ExperimentId | str,
        *,
        decision: DecisionOutcome,
    ) -> Experiment:
        experiment = await self.get(experiment_id)
        seq = await self._next_seq(str(experiment.task_id))
        await self._event_store.append(
            str(experiment.task_id),
            seq - 1,
            (
                _event(
                    str(experiment.task_id),
                    seq,
                    EventType.EXPERIMENT_COMPLETED,
                    {
                        "experiment_id": str(experiment.id),
                        "decision": decision.value,
                    },
                ),
            ),
        )
        return await self.get(experiment.id)

    async def fail(
        self,
        experiment_id: ExperimentId | str,
        *,
        reason: str,
    ) -> Experiment:
        experiment = await self.get(experiment_id)
        seq = await self._next_seq(str(experiment.task_id))
        await self._event_store.append(
            str(experiment.task_id),
            seq - 1,
            (
                _event(
                    str(experiment.task_id),
                    seq,
                    EventType.EXPERIMENT_FAILED,
                    {
                        "experiment_id": str(experiment.id),
                        "reason": reason,
                    },
                ),
            ),
        )
        return await self.get(experiment.id)

    async def invalidate(
        self,
        experiment_id: ExperimentId | str,
        *,
        reason: str,
    ) -> Experiment:
        experiment = await self.get(experiment_id)
        seq = await self._next_seq(str(experiment.task_id))
        await self._event_store.append(
            str(experiment.task_id),
            seq - 1,
            (
                _event(
                    str(experiment.task_id),
                    seq,
                    EventType.EXPERIMENT_INVALIDATED,
                    {
                        "experiment_id": str(experiment.id),
                        "reason": reason,
                    },
                ),
            ),
        )
        return await self.get(experiment.id)

    async def get(self, experiment_id: ExperimentId | str) -> Experiment:
        with self._database.connect() as connection:
            experiment = self._experiment_projection.get(connection, str(experiment_id))
        if experiment is None:
            raise NotFoundError(f"experiment {experiment_id} was not found")
        return experiment

    async def get_for_candidate(self, candidate_id: str) -> Experiment | None:
        with self._database.connect() as connection:
            return self._experiment_projection.get_for_candidate(connection, candidate_id)

    async def list_for_task(self, task_id: TaskId | str) -> list[Experiment]:
        with self._database.connect() as connection:
            return self._experiment_projection.list_for_task(connection, str(task_id))

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
