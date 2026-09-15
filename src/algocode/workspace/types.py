"""Workspace value types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from algocode.domain.model import GitRevision


class WorkspaceKind(StrEnum):
    BASELINE = "baseline"
    CANDIDATE = "candidate"


@dataclass(frozen=True, slots=True)
class Workspace:
    id: str
    kind: WorkspaceKind
    path: Path
    base_revision: GitRevision
    base_snapshot_hash: str


@dataclass(frozen=True, slots=True)
class ApplyResult:
    workspace_id: str
    applied: bool
    reverse_patch_available: bool
    message: str = ""
