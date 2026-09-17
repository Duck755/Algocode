"""Apply and roll back accepted candidates."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from algocode.cli.context import resolve_task_candidate
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.domain.errors import DecisionError
from algocode.domain.model import CandidateStatus, DecisionOutcome

DataDirOption = Annotated[
    Path | None,
    typer.Option("--data-dir", help="Override the data directory."),
]


def apply_command(
    task_id: Annotated[str | None, typer.Argument(help="Task identifier.")] = None,
    candidate_id: Annotated[str | None, typer.Argument(help="Candidate identifier.")] = None,
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Apply an accepted candidate to the user workspace."""

    try:
        context, task, candidate = resolve_task_candidate(task_id, candidate_id, data_dir)
        if candidate is None:
            raise DecisionError("no candidate found for the current task")
        decision = asyncio.run(context.decision_service.get_for_candidate(candidate.id))
        if decision is None or decision.outcome is not DecisionOutcome.ACCEPTED:
            asyncio.run(context.decision_service.accept(task.id, candidate.id))
        result = asyncio.run(context.apply_service.apply(task.id, candidate.id))
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
        task_id=str(task.id),
        candidate_id=str(candidate.id),
        human_lines=(str(result),),
    )


def rollback_command(
    task_id: Annotated[str | None, typer.Argument(help="Task identifier.")] = None,
    candidate_id: Annotated[str | None, typer.Argument(help="Candidate identifier.")] = None,
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Roll back an applied candidate."""

    try:
        context, task, candidate = resolve_task_candidate(task_id, candidate_id, data_dir)
        if candidate is None or candidate.status is not CandidateStatus.APPLIED:
            candidates = asyncio.run(context.candidate_service.list_for_task(task.id))
            candidate = next(
                (item for item in candidates if item.status is CandidateStatus.APPLIED),
                None,
            )
        if candidate is None:
            raise DecisionError("no applied candidate found for the current task")
        result = asyncio.run(context.apply_service.rollback(task.id, candidate.id))
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
        task_id=str(task.id),
        candidate_id=str(candidate.id),
        human_lines=(str(result),),
    )
