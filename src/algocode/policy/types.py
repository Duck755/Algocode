"""Policy request and decision types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class PolicyEffect(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class PolicyLayer(StrEnum):
    HARD = "hard"
    MANAGED = "managed"
    USER = "user"
    PROJECT = "project"
    DEFAULT = "default"


@dataclass(frozen=True, slots=True)
class PolicyRule:
    action: str
    resource: str = "*"
    effect: PolicyEffect = PolicyEffect.ASK
    layer: PolicyLayer = PolicyLayer.PROJECT


@dataclass(frozen=True, slots=True)
class PolicyRequest:
    action: str
    resource: str = "*"
    tool_name: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    effect: PolicyEffect
    reason: str
    layer: PolicyLayer | None = None
    matched_rule: PolicyRule | None = None
