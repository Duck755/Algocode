"""Event envelope and event type vocabulary."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from algocode.domain.model.values import ArtifactRef


class EventType(StrEnum):
    TASK_CREATED = "task.created"
    TASK_PHASE_CHANGED = "task.phase_changed"
    TASK_RETRY_REQUESTED = "task.retry_requested"
    PROJECT_REGISTERED = "project.registered"
    AGENT_TURN_STARTED = "agent.turn_started"
    AGENT_TURN_COMPLETED = "agent.turn_completed"
    AGENT_PHASE_REENTERED = "agent.phase_reentered"
    AGENT_CANCELLED = "agent.cancelled"
    CONTEXT_ASSEMBLED = "context.assembled"
    CONTEXT_COMPACTED = "context.compacted"
    ANALYSIS_COMPLETED = "analysis.completed"
    PLAN_COMPLETED = "plan.completed"
    PHASE_GATE_DENIED = "phase.gate_denied"
    TOOL_CALL_STARTED = "tool.call_started"
    TOOL_CALL_COMPLETED = "tool.call_completed"
    PROJECT_SPEC_LOADED = "project.spec_loaded"
    BASELINE_STARTED = "baseline.started"
    BASELINE_CAPTURED = "baseline.captured"
    BASELINE_FAILED = "baseline.failed"
    CANDIDATE_CREATED = "candidate.created"
    CANDIDATE_FROZEN = "candidate.frozen"
    CANDIDATE_REOPENED = "candidate.reopened"
    CANDIDATE_SELECTED = "candidate.selected"
    CANDIDATE_REJECTED = "candidate.rejected"
    CANDIDATE_APPLIED = "candidate.applied"
    CANDIDATE_ROLLED_BACK = "candidate.rolled_back"
    BUILD_STARTED = "build.started"
    BUILD_SUCCEEDED = "build.succeeded"
    BUILD_FAILED = "build.failed"
    CORRECTNESS_STARTED = "correctness.started"
    CORRECTNESS_PASSED = "correctness.passed"
    CORRECTNESS_FAILED = "correctness.failed"
    EXPERIMENT_CREATED = "experiment.created"
    EXPERIMENT_STARTED = "experiment.started"
    EXPERIMENT_COMPLETED = "experiment.completed"
    EXPERIMENT_FAILED = "experiment.failed"
    EXPERIMENT_INVALIDATED = "experiment.invalidated"
    BENCHMARK_SAMPLES_CAPTURED = "benchmark.samples_captured"
    COMPARISON_PRODUCED = "comparison.produced"
    DECISION_MADE = "decision.made"
    REPORT_GENERATED = "report.generated"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    id: str
    aggregate_id: str
    seq: int
    type: EventType
    schema_version: int = 1
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = field(default_factory=dict)
    artifact_refs: tuple[ArtifactRef, ...] = ()
