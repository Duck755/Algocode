"""Shared CLI options and structured output helpers."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from typing import Annotated, Any

import typer

JsonOption = Annotated[
    bool,
    typer.Option("--json", help="Emit machine-readable JSON."),
]
NoColorOption = Annotated[
    bool,
    typer.Option("--no-color", help="Disable ANSI color output."),
]
QuietOption = Annotated[
    bool,
    typer.Option("--quiet", help="Suppress non-essential human-readable output."),
]
VerboseOption = Annotated[
    bool,
    typer.Option("--verbose", help="Emit diagnostic details to stderr."),
]
ProgressOption = Annotated[
    bool | None,
    typer.Option(
        "--progress/--no-progress",
        help="Force the live stage rail on or off.",
    ),
]
YesOption = Annotated[
    bool,
    typer.Option("--yes", "-y", help="Skip the confirmation prompt."),
]


def is_interactive() -> bool:
    """Return True when both stdin and stdout are attached to a terminal."""
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def emit_result(
    command: str,
    *,
    data: Any = None,
    json_output: bool,
    quiet: bool = False,
    verbose: bool = False,
    no_color: bool = False,
    status: str = "completed",
    message: str = "",
    task_id: str | None = None,
    candidate_id: str | None = None,
    experiment_id: str | None = None,
    artifacts: Iterable[Any] = (),
    human_lines: Iterable[str] = (),
) -> None:
    """Emit one command result using the stable CLI envelope."""

    artifact_values = list(artifacts)
    if json_output:
        payload = {
            "ok": True,
            "command": command,
            "status": status,
            "task_id": task_id,
            "candidate_id": candidate_id,
            "experiment_id": experiment_id,
            "artifacts": artifact_values,
            "message": message,
            "data": data,
        }
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    if quiet:
        return
    for line in human_lines:
        typer.echo(line)
    if verbose:
        typer.echo(
            f"[verbose] command={command} status={status} no_color={no_color}",
            err=True,
        )