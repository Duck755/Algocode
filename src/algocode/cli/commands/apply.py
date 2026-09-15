"""Apply and roll back accepted candidates."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from algocode.cli.context import build_task_context
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.domain.errors import DecisionError

DataDirOption = Annotated[
    Path | None,
    typer.Option("--data-dir", help="Override the data directory."),
]


def apply_command(
    task_id: Annotated[str, typer.Argument(help="Task identifier.")],
    candidate_id: Annotated[str, typer.Argument(help="Candidate identifier.")],
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Apply an accepted candidate to the user workspace."""

    try:
        result = asyncio.run(
            build_task_context(task_id, data_dir).apply_service.apply(task_id, candidate_id)
        )
    except DecisionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    emit_result(
        "apply",
        data=result,
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        status="applied" if result.get("applied") else "failed",
        task_id=task_id,
        candidate_id=candidate_id,
        human_lines=(str(result),),
    )


def rollback_command(
    task_id: Annotated[str, typer.Argument(help="Task identifier.")],
    candidate_id: Annotated[str, typer.Argument(help="Candidate identifier.")],
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Roll back an applied candidate."""

    try:
        result = asyncio.run(
            build_task_context(task_id, data_dir).apply_service.rollback(task_id, candidate_id)
        )
    except DecisionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    emit_result(
        "rollback",
        data=result,
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        status="rolled_back" if result.get("rolled_back") else "failed",
        task_id=task_id,
        candidate_id=candidate_id,
        human_lines=(str(result),),
    )
