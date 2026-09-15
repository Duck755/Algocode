"""Approval request and decision types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ApprovalScope(StrEnum):
    ONCE = "once"
    TASK = "task"
    PROJECT = "project"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    task_id: str
    project_id: str
    action: str
    resource: str
    reason: str


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    approved: bool
    scope: ApprovalScope
    reason: str = ""
