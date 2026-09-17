"""Show the current candidate patch."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from algocode.cli.context import resolve_task_candidate
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.workspace import GitRepository

DataDirOption = Annotated[
    Path | None,
    typer.Option("--data-dir", help="Override the data directory."),
]


def diff_command(
    task_id: Annotated[str | None, typer.Argument(help="Task identifier.")] = None,
    candidate_id: Annotated[
        str | None,
        typer.Option("--candidate-id", help="Candidate identifier."),
    ] = None,
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Print the patch in the current candidate workspace."""

    try:
        _context, _task, candidate = resolve_task_candidate(task_id, candidate_id, data_dir)
    except Exception as exc:  # noqa: BLE001
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if candidate is None:
        typer.echo("no candidate found for the current task", err=True)
        raise typer.Exit(code=1)

    repository = asyncio.run(GitRepository.discover(candidate.workspace_ref))
    workspace = Path(candidate.workspace_ref)
    snapshot = asyncio.run(repository.capture_snapshot(workspace))
    patch = snapshot.patch.decode(errors="replace")
    untracked = [item.relative_path for item in snapshot.untracked]
    if json_output:
        emit_result(
            "diff",
            data={
                "candidateId": str(candidate.id),
                "workspace": str(workspace),
                "patch": patch,
                "untracked": untracked,
            },
            json_output=True,
            no_color=no_color,
            quiet=quiet,
            verbose=verbose,
            task_id=str(candidate.task_id),
            candidate_id=str(candidate.id),
        )
        return
    if patch:
        typer.echo(patch.rstrip())
    if untracked:
        typer.echo("\nUntracked files:")
        for path in untracked:
            typer.echo(f"  {path}")
    if not patch and not untracked:
        typer.echo("candidate has no changes")
