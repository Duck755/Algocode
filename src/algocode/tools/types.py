"""Tool definitions, execution context, and results."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from algocode.domain.model import ArtifactRef, Task, TaskPhase
from algocode.languages.types import BuildProfile

ToolStatus = Literal["success", "error", "interrupted"]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, object]
    output_schema: dict[str, object] = field(default_factory=dict)
    effects: str = "read"
    idempotent: bool = True
    parallelizable: bool = True
    permission: str = "allow"
    timeout_seconds: int = 30


@dataclass(frozen=True, slots=True)
class ToolResult:
    status: ToolStatus
    summary: str
    structured: dict[str, object] = field(default_factory=dict)
    artifact_refs: tuple[ArtifactRef, ...] = ()
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class ToolContext:
    task: Task
    phase: TaskPhase
    workspace: Path
    candidate_id: str | None = None
    correctness_result_id: str | None = None
    artifact_store: Any = None
    language_registry: Any = None
    correctness_service: Any = None
    benchmark_service: Any = None
    candidate_service: Any = None
    resource_provider: Any = None
    build_profile: BuildProfile = field(default_factory=BuildProfile)
    protected_files: tuple[str, ...] = ()
