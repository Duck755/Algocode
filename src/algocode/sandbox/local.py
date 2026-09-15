"""Local process sandbox policy."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from algocode.config.model import SandboxConfig


@dataclass(frozen=True, slots=True)
class SandboxRequest:
    action: str
    workspace: Path
    network: bool = False


@dataclass(frozen=True, slots=True)
class SandboxDecision:
    allowed: bool
    reason: str
    environment: dict[str, str] = field(default_factory=dict)


class LocalProcessSandbox:
    """Apply local process restrictions without changing tool semantics."""

    def __init__(self, config: SandboxConfig, runner=None) -> None:
        self.config = config
        self.runner = runner

    def authorize(self, request: SandboxRequest) -> SandboxDecision:
        if self.runner is not None and self.runner.backend == "disabled":
            return SandboxDecision(
                allowed=False,
                reason="sandbox backend is unavailable or disabled",
            )
        if request.network and not self.config.network:
            return SandboxDecision(
                allowed=False,
                reason="sandbox network access is disabled",
            )
        workspace = request.workspace.resolve()
        if not workspace.exists():
            return SandboxDecision(
                allowed=False,
                reason=f"sandbox workspace does not exist: {workspace}",
            )
        environment = self._sanitized_environment()
        return SandboxDecision(
            allowed=True,
            reason=f"local process sandbox mode {self.config.mode}",
            environment=environment,
        )

    def _sanitized_environment(self) -> dict[str, str]:
        allowed = {name.upper() for name in self.config.allowed_env}
        environment = {
            name: value
            for name, value in os.environ.items()
            if name.upper() in allowed and not _is_secret_name(name)
        }
        return environment


def _is_secret_name(name: str) -> bool:
    normalized = name.upper()
    return any(
        marker in normalized for marker in ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
    )
