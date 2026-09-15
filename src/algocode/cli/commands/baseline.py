"""Capture a baseline for a task."""

from __future__ import annotations

import asyncio
import shlex
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any

import typer

from algocode.cli.context import build_task_context
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.domain.errors import BaselineBuildFailed, BaselineError, NotFoundError
from algocode.domain.model import Baseline
from algocode.workspace.git import GitError

DataDirOption = Annotated[
    Path | None,
    typer.Option("--data-dir", help="Override the data directory."),
]


def _baseline_payload(baseline: Baseline) -> dict[str, Any]:
    payload = asdict(baseline)
    payload["revision"] = baseline.revision.value
    payload["created_at"] = baseline.created_at.isoformat()
    return payload


def baseline_command(
    task_id: Annotated[str, typer.Argument(help="Task identifier.")],
    language: Annotated[
        str,
        typer.Option("--language", help="auto, cpp, or python."),
    ] = "auto",
    source_root: Annotated[
        str,
        typer.Option("--source-root", help="Source root relative to the repository."),
    ] = ".",
    build_command: Annotated[
        str | None,
        typer.Option("--build-command", help="Override the project build command."),
    ] = None,
    timeout_seconds: Annotated[
        int,
        typer.Option("--timeout", min=1, help="Build timeout in seconds."),
    ] = 120,
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Create an isolated baseline workspace and build it."""

    context = build_task_context(task_id, data_dir)
    commands: tuple[tuple[str, ...], ...] = ()
    if build_command:
        commands = (tuple(shlex.split(build_command)),)
    try:
        baseline = asyncio.run(
            context.baseline_service.capture(
                task_id,
                language=language,
                source_root=source_root,
                commands=commands,
                timeout_seconds=timeout_seconds,
            )
        )
    except BaselineBuildFailed as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=4) from exc
    except (BaselineError, GitError, NotFoundError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc

    payload = _baseline_payload(baseline)
    emit_result(
        "baseline",
        data=payload,
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        task_id=str(baseline.task_id),
        human_lines=(
            f"Baseline: {baseline.id}",
            f"Task: {baseline.task_id}",
            f"Revision: {baseline.revision.value}",
            f"Snapshot: {baseline.snapshot_hash}",
            f"Environment: {baseline.environment_hash}",
            *(
                (f"Build artifact: {baseline.build_result_ref.uri}",)
                if baseline.build_result_ref is not None
                else ()
            ),
        ),
    )
