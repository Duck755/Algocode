"""Retry a task from PLAN using persisted optimization history."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import typer

from algocode.application.services.project_state import find_current_task
from algocode.cli.commands.optimize import DataDirOption, optimize_command
from algocode.cli.context import build_task_context, resolve_data_dir
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption
from algocode.domain.events import EventEnvelope, EventType
from algocode.runtime.optimization_record import OptimizationRecordStore


def _append_retry_request(context, task_id: str, record_count: int) -> None:
    events = asyncio.run(context.event_store.read(str(task_id)))
    seq = events[-1].seq + 1 if events else 1
    event = EventEnvelope(
        id=f"evt_{uuid4().hex}",
        aggregate_id=str(task_id),
        seq=seq,
        type=EventType.TASK_RETRY_REQUESTED,
        timestamp=datetime.now(UTC),
        payload={
            "retry_id": f"retry_{uuid4().hex}",
            "record_count": record_count,
            "requested_at": datetime.now(UTC).isoformat(),
        },
    )
    asyncio.run(context.event_store.append(str(task_id), seq - 1, (event,)))


def retry_command(
    task_id: Annotated[
        str | None,
        typer.Argument(help="Task identifier. Defaults to .algocode/current-task.json."),
    ] = None,
    fake_provider: Annotated[
        bool,
        typer.Option("--fake-provider", help="Use the deterministic provider without API keys."),
    ] = False,
    provider_key: Annotated[
        str | None,
        typer.Option("--provider", help="Configured provider key. Defaults to project default."),
    ] = None,
    model_key: Annotated[
        str | None,
        typer.Option("--model", help="Configured model key. Defaults to project default."),
    ] = None,
    max_steps: Annotated[
        int | None,
        typer.Option("--max-steps", min=1, help="Maximum model turns per phase."),
    ] = None,
    max_tool_calls: Annotated[
        int | None,
        typer.Option("--max-tool-calls", min=1, help="Maximum tool calls per phase."),
    ] = None,
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Start a new PLAN cycle with previous optimization records in context."""

    current_state = find_current_task(Path.cwd())
    if task_id is None:
        if current_state is None or not current_state.get("taskId"):
            typer.echo("no current task found; run algocode init or pass a task id", err=True)
            raise typer.Exit(code=2)
        task_id = str(current_state["taskId"])

    context = build_task_context(task_id, resolve_data_dir(data_dir))
    task = asyncio.run(context.task_service.get_task(task_id))
    store = OptimizationRecordStore(
        context.data_dir / "optimization-records",
        redactor=context.secret_redactor,
    )
    records = store.list_records(task_id=str(task.id))
    if not records:
        typer.echo("no optimization records found for the current task", err=True)
        raise typer.Exit(code=2)

    _append_retry_request(context, str(task.id), len(records))
    optimize_command(
        task_id=task_id,
        fake_provider=fake_provider,
        provider_key=provider_key,
        model_key=model_key,
        candidate_workspace=None,
        candidate_id=None,
        max_steps=max_steps,
        max_tool_calls=max_tool_calls,
        stop_after="report",
        data_dir=data_dir,
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        command_name_override="retry",
    )
