"""Candidate workspace commands."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any

import typer

from algocode.bootstrap import build_context
from algocode.cli.context import resolve_data_dir
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.domain.errors import NotFoundError
from algocode.domain.model import Candidate

candidate_app = typer.Typer(
    name="candidate",
    help="Create and inspect candidate workspaces.",
    no_args_is_help=True,
)

DataDirOption = Annotated[
    Path | None,
    typer.Option("--data-dir", help="Override the data directory."),
]


def _payload(candidate: Candidate) -> dict[str, Any]:
    payload = asdict(candidate)
    payload["base_revision"] = candidate.base_revision.value
    payload["apply_base_revision"] = (
        candidate.apply_base_revision.value if candidate.apply_base_revision is not None else None
    )
    payload["created_at"] = candidate.created_at.isoformat()
    payload["frozen_at"] = candidate.frozen_at.isoformat() if candidate.frozen_at else None
    return payload


def _emit_candidate(
    command: str,
    candidate: Candidate,
    json_output: bool,
    no_color: bool,
    quiet: bool,
    verbose: bool,
) -> None:
    emit_result(
        command,
        data=_payload(candidate),
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        task_id=str(candidate.task_id),
        candidate_id=str(candidate.id),
        human_lines=(
            f"Candidate: {candidate.id}",
            f"Status: {candidate.status.value}",
            f"Workspace: {candidate.workspace_ref}",
            f"Patch hash: {candidate.patch_hash}",
        ),
    )


@candidate_app.command("create")
def create_candidate(
    task_id: Annotated[str, typer.Argument(help="Task identifier.")],
    base_revision: Annotated[
        str | None,
        typer.Option("--base-revision", help="Override the baseline revision."),
    ] = None,
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Create a candidate worktree from the task baseline."""

    candidate = asyncio.run(
        build_context(data_dir=resolve_data_dir(data_dir)).candidate_service.create(
            task_id,
            base_revision=base_revision,
        )
    )
    _emit_candidate("candidate.create", candidate, json_output, no_color, quiet, verbose)


@candidate_app.command("freeze")
def freeze_candidate(
    candidate_id: Annotated[str, typer.Argument(help="Candidate identifier.")],
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Freeze candidate edits and record the patch hash."""

    candidate = asyncio.run(
        build_context(data_dir=resolve_data_dir(data_dir)).candidate_service.freeze(candidate_id)
    )
    _emit_candidate("candidate.freeze", candidate, json_output, no_color, quiet, verbose)


@candidate_app.command("list")
def list_candidates(
    task_id: Annotated[str, typer.Argument(help="Task identifier.")],
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """List candidates belonging to a task."""

    candidates = asyncio.run(
        build_context(data_dir=resolve_data_dir(data_dir)).candidate_service.list_for_task(task_id)
    )
    emit_result(
        "candidate.list",
        data=[_payload(item) for item in candidates],
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        task_id=task_id,
        human_lines=tuple(
            f"{candidate.id}\t{candidate.status.value}\t{candidate.workspace_ref}"
            for candidate in candidates
        ),
    )


@candidate_app.command("show")
def show_candidate(
    candidate_id: Annotated[str, typer.Argument(help="Candidate identifier.")],
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Show one candidate."""

    try:
        candidate = asyncio.run(
            build_context(data_dir=resolve_data_dir(data_dir)).candidate_service.get(candidate_id)
        )
    except NotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    _emit_candidate("candidate.show", candidate, json_output, no_color, quiet, verbose)
