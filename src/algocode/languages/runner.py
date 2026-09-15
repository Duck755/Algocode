"""Asynchronous process execution for language adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from algocode.sandbox.runner import SandboxProcessRunner


@dataclass(frozen=True, slots=True)
class CommandResult:
    command: tuple[str, ...]
    exit_code: int
    stdout: bytes
    stderr: bytes
    duration_seconds: float
    truncated: bool = False


async def run_command(
    command: tuple[str, ...],
    *,
    cwd: Path,
    timeout_seconds: int,
    sandbox_runner: SandboxProcessRunner | None = None,
    extra_env: dict[str, str] | None = None,
) -> CommandResult:
    """Run one command through the restricted process runner."""

    runner = sandbox_runner or SandboxProcessRunner()
    result = await runner.run(
        command,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        extra_env=extra_env,
    )
    return CommandResult(
        command=command,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_seconds=result.duration_seconds,
        truncated=result.truncated,
    )


async def run_commands(
    commands: tuple[tuple[str, ...], ...],
    *,
    cwd: Path,
    timeout_seconds: int,
    sandbox_runner: SandboxProcessRunner | None = None,
    extra_env: dict[str, str] | None = None,
) -> tuple[CommandResult, ...]:
    results: list[CommandResult] = []
    for command in commands:
        result = await run_command(
            command,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            sandbox_runner=sandbox_runner,
            extra_env=extra_env,
        )
        results.append(result)
        if result.exit_code != 0:
            break
    return tuple(results)
