"""Opt-in controlled shell tool.

The shell tool is intentionally not part of :func:`algocode.tools.build_default_registry`.
Deployments may register it only when a strong sandbox is available and the operator
has explicitly enabled it.
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path

from algocode.tools.types import ToolContext, ToolDefinition, ToolResult

SHELL_TIMEOUT_SECONDS = 120


async def run_shell(context: ToolContext, arguments: dict[str, object]) -> ToolResult:
    command = str(arguments.get("command", "")).strip()
    if not command:
        return ToolResult(status="error", summary="command must not be empty")
    working_directory = _resolve_cwd(context, arguments)
    if working_directory is None:
        return ToolResult(status="error", summary="working_directory escapes the workspace")

    runner = _runner(context)
    if runner is None:
        return ToolResult(status="error", summary="sandbox runner is unavailable")

    try:
        argv = tuple(shlex.split(command, posix=os.name != "nt"))
    except ValueError as exc:
        return ToolResult(status="error", summary=f"invalid shell command: {exc}")
    if not argv:
        return ToolResult(status="error", summary="command must not be empty")

    timeout = _timeout(arguments)
    input_bytes = str(arguments.get("input", "")).encode(errors="replace")
    result = await runner.run(
        argv,
        cwd=working_directory,
        timeout_seconds=timeout,
        input_bytes=input_bytes,
    )
    return ToolResult(
        status="success" if result.exit_code == 0 and not result.timed_out else "error",
        summary=f"shell exited with {result.exit_code}",
        structured={
            "command": list(argv),
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "start_failed": result.start_failed,
            "backend": result.backend,
            "stdout": result.stdout.decode(errors="replace"),
            "stderr": result.stderr.decode(errors="replace"),
            "duration_seconds": result.duration_seconds,
        },
        truncated=result.truncated,
    )


def shell_definition() -> ToolDefinition:
    return ToolDefinition(
        name="run_shell",
        description=(
            "Execute one shell command inside the sandboxed candidate workspace. "
            "Use only for non-destructive investigation or small build/test steps."
        ),
        input_schema={
            "command": {"type": "string", "required": True},
            "working_directory": {"type": "string", "required": False},
            "input": {"type": "string", "required": False},
            "timeout_seconds": {"type": "integer", "required": False},
        },
        effects="execute",
        idempotent=False,
        parallelizable=False,
        permission="allow",
        timeout_seconds=SHELL_TIMEOUT_SECONDS,
    )


def register_shell_tool(registry) -> None:
    registry.register(shell_definition(), run_shell)


def _runner(context: ToolContext):
    if context.language_registry is None:
        return None
    return getattr(context.language_registry, "sandbox_runner", None)


def _resolve_cwd(context: ToolContext, arguments: dict[str, object]) -> Path | None:
    relative = arguments.get("working_directory")
    if relative is None:
        return context.workspace
    root = context.workspace.resolve()
    target = (root / str(relative)).resolve()
    if not target.is_relative_to(root):
        return None
    return target


def _timeout(arguments: dict[str, object]) -> int:
    raw = arguments.get("timeout_seconds")
    try:
        value = int(raw) if raw is not None else SHELL_TIMEOUT_SECONDS
    except (TypeError, ValueError):
        return SHELL_TIMEOUT_SECONDS
    return max(1, min(value, SHELL_TIMEOUT_SECONDS))
