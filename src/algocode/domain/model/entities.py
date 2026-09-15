"""Domain entities for the optimization workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from algocode.domain.model.enums import (
    BenchmarkStatus,
    CandidateStatus,
    CorrectnessStatus,
    DecisionOutcome,
    ExperimentStatus,
    FailureKind,
    Language,
    TaskPhase,
    TaskStatus,
)
from algocode.domain.model.ids import (
    CandidateId,
    DecisionId,
    ExperimentId,
    ProjectId,
    TaskId,
)
from algocode.domain.model.values import ArtifactRef, GitRevision


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class Project:
    id: ProjectId
    root_path: str
    name: str
    language: Language
    git_revision: str
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class Baseline:
    id: str
    task_id: TaskId
    revision: GitRevision
    snapshot_hash: str
    environment_hash: str
    build_result_ref: ArtifactRef | None = None
    correctness_result_ref: ArtifactRef | None = None
    benchmark_result_ref: ArtifactRef | None = None
    workspace_ref: str | None = None
    created_at: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class Candidate:
    id: CandidateId
    task_id: TaskId
    base_revision: GitRevision
    base_snapshot_hash: str
    workspace_ref: str
    status: CandidateStatus = CandidateStatus.GENERATED
    patch_hash: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    frozen_at: datetime | None = None


@dataclass(slots=True)
class CorrectnessRun:
    id: str
    task_id: TaskId
    target_kind: str
    target_id: str
    workspace_ref: str
    spec_hash: str
    status: CorrectnessStatus
    spec_ref: ArtifactRef
    result_ref: ArtifactRef | None = None
    failure_kind: FailureKind | None = None
    started_at: datetime = field(default_factory=utcnow)
    completed_at: datetime | None = None


@dataclass(slots=True)
class Experiment:
    id: ExperimentId
    task_id: TaskId
    baseline_id: str
    candidate_id: CandidateId
    spec_hash: str
    input_hash: str
    environment_hash: str
    comparison_key: str
    policy_hash: str
    status: ExperimentStatus = ExperimentStatus.CREATED
    decision: DecisionOutcome | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    invalidation_reason: str | None = None


@dataclass(slots=True)
class BenchmarkRun:
    id: str
    task_id: TaskId
    target_kind: str
    target_id: str
    workspace_ref: str
    spec_hash: str
    input_hash: str
    environment_hash: str
    comparison_key: str
    status: BenchmarkStatus
    result_ref: ArtifactRef | None = None
    comparison_ref: ArtifactRef | None = None
    correctness_result_id: str | None = None
    started_at: datetime = field(default_factory=utcnow)
    completed_at: datetime | None = None


@dataclass(slots=True)
class Decision:
    id: DecisionId
    task_id: TaskId
    candidate_id: CandidateId
    experiment_ids: list[ExperimentId] = field(default_factory=list)
    outcome: DecisionOutcome = DecisionOutcome.INCONCLUSIVE
    reason: str = ""
    evidence_refs: list[ArtifactRef] = field(default_factory=list)
    decided_at: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class Task:
    id: TaskId
    project_id: ProjectId
    objective: str
    status: TaskStatus = TaskStatus.DRAFT
    current_phase: TaskPhase = TaskPhase.CREATE
    baseline_id: str | None = None
    active_candidate_id: CandidateId | None = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    completed_at: datetime | None = None
