"""CLI commands for task creation and inspection."""

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
from algocode.domain.model import Task

task_app = typer.Typer(
    name="task",
    help="Create and inspect optimization tasks.",
    no_args_is_help=True,
)

DataDirOption = Annotated[
    Path | None,
    typer.Option("--data-dir", help="Override the data directory."),
]


def _task_payload(task: Task) -> dict[str, Any]:
    payload = asdict(task)
    for key, value in payload.items():
        if hasattr(value, "isoformat"):
            payload[key] = value.isoformat()
    return payload


def _emit_task(
    command: str,
    task: Task,
    json_output: bool,
    no_color: bool,
    quiet: bool,
    verbose: bool,
) -> None:
    payload = _task_payload(task)
    emit_result(
        command,
        data=payload,
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        task_id=str(task.id),
        human_lines=(
            f"Task: {task.id}",
            f"Project: {task.project_id}",
            f"Status: {task.status.value}",
            f"Phase: {task.current_phase.value}",
            f"Objective: {task.objective}",
            f"Created: {task.created_at.isoformat()}",
            f"Updated: {task.updated_at.isoformat()}",
        ),
    )


@task_app.command("create")
def create_task(
    objective: Annotated[str, typer.Option("--objective", help="Optimization objective.")],
    project_id: Annotated[
        str | None,
        typer.Option("--project-id", help="Existing project identifier."),
    ] = None,
    project_root: Annotated[
        Path,
        typer.Option("--project-root", help="Registered project root."),
    ] = Path("."),
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Create a new task and its initial durable event."""

    data_dir = resolve_data_dir(data_dir, start=project_root)
    context = build_context(project_root=project_root, data_dir=data_dir)
    if project_id is None:
        project = asyncio.run(context.project_service.get_by_root(project_root))
        if project is not None:
            project_id = project.id
    task = asyncio.run(context.task_service.create_task(objective=objective, project_id=project_id))
    _emit_task("task.create", task, json_output, no_color, quiet, verbose)


@task_app.command("list")
def list_tasks(
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """List tasks from the local read model."""

    tasks = asyncio.run(
        build_context(data_dir=resolve_data_dir(data_dir)).task_service.list_tasks()
    )
    data = [_task_payload(task) for task in tasks]
    emit_result(
        "task.list",
        data=data,
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        human_lines=(
            ("No tasks found.",)
            if not tasks
            else tuple(
                f"{task.id}\t{task.status.value}\t{task.current_phase.value}\t{task.objective}"
                for task in tasks
            )
        ),
    )


@task_app.command("show")
def show_task(
    task_id: Annotated[str, typer.Argument(help="Task identifier.")],
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Show one task by identifier."""

    try:
        task = asyncio.run(
            build_context(data_dir=resolve_data_dir(data_dir)).task_service.get_task(task_id)
        )
    except NotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    _emit_task("task.show", task, json_output, no_color, quiet, verbose)
