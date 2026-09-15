"""Inspect benchmark-backed experiments."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Annotated, Any

import typer

from algocode.application.services.benchmark_service import BenchmarkService
from algocode.bootstrap import build_context
from algocode.cli.context import build_task_context
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.domain.errors import BenchmarkError, NotFoundError
from algocode.domain.model import BenchmarkRun

experiment_app = typer.Typer(
    name="experiment",
    help="List and inspect benchmark experiments.",
    no_args_is_help=True,
)


def _experiment_payload(run: BenchmarkRun) -> dict[str, Any]:
    return {
        "experiment_id": run.id,
        "task_id": str(run.task_id),
        "target_kind": run.target_kind,
        "target_id": run.target_id,
        "status": run.status.value,
        "spec_hash": run.spec_hash,
        "input_hash": run.input_hash,
        "environment_hash": run.environment_hash,
        "comparison_key": run.comparison_key,
        "correctness_result_id": run.correctness_result_id,
        "started_at": run.started_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "has_result": run.result_ref is not None,
        "has_comparison": run.comparison_ref is not None,
    }


@experiment_app.command("list")
def list_experiments(
    task_id: Annotated[
        str | None,
        typer.Argument(help="Only list experiments for this task."),
    ] = None,
    status: Annotated[
        str | None,
        typer.Option("--status", help="Filter by benchmark status."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, help="Maximum number of experiments."),
    ] = 100,
    data_dir: Annotated[
        str | None,
        typer.Option("--data-dir", help="Override the data directory."),
    ] = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """List experiments from the durable benchmark read model."""

    service = _benchmark_service(data_dir, task_id=task_id)
    runs = (
        asyncio.run(service.list_for_task(task_id)) if task_id else asyncio.run(service.list_all())
    )
    if status:
        runs = [run for run in runs if run.status.value == status]
    runs = runs[:limit]
    data = [_experiment_payload(run) for run in runs]
    emit_result(
        "experiment.list",
        data=data,
        json_output=json_output,
        quiet=quiet,
        verbose=verbose,
        no_color=no_color,
        human_lines=(
            ("No experiments found.",)
            if not runs
            else tuple(
                f"{run.id}\t{run.status.value}\t{run.target_kind}:{run.target_id}" for run in runs
            )
        ),
    )


@experiment_app.command("show")
def show_experiment(
    experiment_id: Annotated[str, typer.Argument(help="Experiment identifier.")],
    data_dir: Annotated[
        str | None,
        typer.Option("--data-dir", help="Override the data directory."),
    ] = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Show one experiment and its result/comparison artifacts."""

    service = _benchmark_service(data_dir)
    try:
        run = asyncio.run(service.get(experiment_id))
        result = asyncio.run(service.read_result(run)) if run.result_ref is not None else None
        comparison = asyncio.run(service.read_comparison(run))
    except (BenchmarkError, NotFoundError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=5) from exc
    data = {
        "experiment": _experiment_payload(run),
        "result": result,
        "comparison": comparison,
    }
    artifacts = [asdict(ref) for ref in (run.result_ref, run.comparison_ref) if ref is not None]
    emit_result(
        "experiment.show",
        data=data,
        json_output=json_output,
        quiet=quiet,
        verbose=verbose,
        no_color=no_color,
        task_id=str(run.task_id),
        experiment_id=run.id,
        artifacts=artifacts,
        human_lines=(
            f"Experiment: {run.id}",
            f"Task: {run.task_id}",
            f"Target: {run.target_kind}:{run.target_id}",
            f"Status: {run.status.value}",
        ),
    )


def _benchmark_service(
    data_dir: str | None,
    *,
    task_id: str | None = None,
) -> BenchmarkService:
    context = (
        build_task_context(task_id, data_dir)
        if task_id is not None
        else build_context(data_dir=data_dir)
    )
    return context.benchmark_service
