"""Evaluation task, result, and comparison types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ExpectedBehavior(StrEnum):
    OPTIMIZATION = "expect_optimization"
    NO_OPTIMIZATION = "expect_no_optimization"
    REJECT = "expect_reject"
    RECOVERY = "expect_recovery"
    POLICY_DENY = "expect_policy_deny"


@dataclass(frozen=True, slots=True)
class EvalTask:
    id: str
    language: str
    category: str
    difficulty: str
    objective: str
    files: dict[str, str]
    expected_behavior: ExpectedBehavior
    correctness_spec: dict[str, Any] | None = None
    candidate_correctness_spec: dict[str, Any] | None = None
    benchmark_spec: dict[str, Any] | None = None
    protected_files: tuple[str, ...] = ()
    candidate_patch: str | None = None
    protected_patch: bool = False
    max_steps: int = 10
    max_tool_calls: int = 30


@dataclass(frozen=True, slots=True)
class EvalTaskResult:
    task_id: str
    passed: bool
    expected_behavior: str
    actual_behavior: str
    duration_seconds: float
    turns: int
    tool_calls: int
    metrics: dict[str, float | int | str | None] = field(default_factory=dict)
    message: str = ""


@dataclass(frozen=True, slots=True)
class EvalRun:
    run_id: str
    suite: str
    provider: str
    model: str
    seed: int
    repeat_count: int
    config_hash: str
    tool_catalog_hash: str
    environment_hash: str
    results: tuple[EvalTaskResult, ...]
    aggregate: dict[str, float | int | str | None]
    duration_seconds: float


@dataclass(frozen=True, slots=True)
class EvalComparison:
    baseline_run_id: str
    candidate_run_id: str
    baseline_provider: str
    candidate_provider: str
    pass_rate_delta: float
    average_turns_delta: float
    average_tool_calls_delta: float
    duration_delta_seconds: float
    improved: bool
