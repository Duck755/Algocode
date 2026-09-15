"""Run, compare, and inspect benchmarks."""

from __future__ import annotations

import asyncio
import shlex
from pathlib import Path
from typing import Annotated, Any

import typer

from algocode.benchmark.spec import load_benchmark_spec
from algocode.benchmark.types import BenchmarkResult, ComparisonResult
from algocode.cli.context import build_task_context
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.domain.errors import (
    BenchmarkError,
    ConfigError,
    CorrectnessError,
    NotFoundError,
    ResourceBusyError,
)
from algocode.domain.model import BenchmarkRun
from algocode.languages.types import BuildProfile

DataDirOption = Annotated[
    Path | None,
    typer.Option("--data-dir", help="Override the data directory."),
]


def _run_payload(
    run: BenchmarkRun,
    result: BenchmarkResult,
    comparison: ComparisonResult | None,
) -> dict[str, Any]:
    summary = (
        None
        if result.summary is None
        else {
            "count": result.summary.count,
            "median": result.summary.median,
            "minimum": result.summary.minimum,
            "maximum": result.summary.maximum,
            "mean": result.summary.mean,
            "stddev": result.summary.stddev,
            "variation_percent": result.summary.variation_percent,
        }
    )
    return {
        "run_id": run.id,
        "task_id": str(run.task_id),
        "target_kind": run.target_kind,
        "target_id": run.target_id,
        "status": run.status.value,
        "spec_hash": run.spec_hash,
        "input_hash": run.input_hash,
        "environment_hash": run.environment_hash,
        "comparison_key": run.comparison_key,
        "valid": result.valid,
        "message": result.message,
        "summary": summary,
        "samples": [
            {
                "target_kind": sample.target_kind,
                "target_id": sample.target_id,
                "phase": sample.phase,
                "index": sample.index,
                "metric": sample.metric.value,
                "value": sample.value,
                "valid": sample.valid,
            }
            for sample in result.samples
        ],
        "comparison": (
            None
            if comparison is None
            else {
                "baseline_median": comparison.baseline_median,
                "candidate_median": comparison.candidate_median,
                "improvement_percent": comparison.improvement_percent,
                "valid": comparison.valid,
                "reason": comparison.reason,
            }
        ),
    }


def benchmark_command(
    task_id: Annotated[str, typer.Argument(help="Task identifier.")],
    spec_path: Annotated[
        Path | None,
        typer.Option("--spec", help="Benchmark specification YAML file."),
    ] = None,
    candidate_id: Annotated[
        str | None,
        typer.Option("--candidate-id", help="Candidate identifier."),
    ] = None,
    workspace: Annotated[
        Path | None,
        typer.Option("--workspace", help="Candidate workspace path."),
    ] = None,
    correctness_result: Annotated[
        str | None,
        typer.Option("--correctness-result", help="Passed candidate correctness result."),
    ] = None,
    show: Annotated[
        str | None,
        typer.Option("--show", help="Show a stored benchmark result."),
    ] = None,
    build_command: Annotated[
        str | None,
        typer.Option("--build-command", help="Override the project build command."),
    ] = None,
    source_root: Annotated[
        str,
        typer.Option("--source-root", help="Source root relative to the workspace."),
    ] = ".",
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
    """Benchmark a baseline, or compare a candidate against its baseline."""

    context = build_task_context(task_id, data_dir)
    if show is not None:
        try:
            run = asyncio.run(context.benchmark_service.get(show))
            payload = asyncio.run(context.benchmark_service.read_result(run))
        except (BenchmarkError, NotFoundError) as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=5) from exc
        emit_result(
            "benchmark.show",
            data=payload,
            json_output=json_output,
            no_color=no_color,
            quiet=quiet,
            verbose=verbose,
            status=run.status.value,
            task_id=str(run.task_id),
            experiment_id=run.id,
            human_lines=(
                f"Benchmark: {run.id}",
                f"Target: {run.target_kind} {run.target_id}",
                f"Status: {run.status.value}",
            ),
        )
        return
    if spec_path is None:
        typer.echo("--spec is required unless --show is used", err=True)
        raise typer.Exit(code=2)
    candidate_values = (candidate_id, workspace, correctness_result)
    if any(value is not None for value in candidate_values) and not all(
        value is not None for value in candidate_values
    ):
        typer.echo(
            "candidate mode requires --candidate-id, --workspace, and --correctness-result",
            err=True,
        )
        raise typer.Exit(code=2)
    commands: tuple[tuple[str, ...], ...] = ()
    if build_command:
        commands = (tuple(shlex.split(build_command)),)
    profile = BuildProfile(
        commands=commands,
        source_root=source_root,
        timeout_seconds=timeout_seconds,
    )
    try:
        spec = load_benchmark_spec(spec_path)
        if candidate_id is not None:
            assert workspace is not None
            assert correctness_result is not None
            run, result, comparison = asyncio.run(
                context.benchmark_service.run_candidate(
                    task_id,
                    candidate_id,
                    workspace,
                    correctness_result,
                    spec,
                    build_profile=profile,
                )
            )
        else:
            run, result = asyncio.run(
                context.benchmark_service.run_baseline(
                    task_id,
                    spec,
                    build_profile=profile,
                )
            )
            comparison = None
    except (BenchmarkError, ConfigError, CorrectnessError, ResourceBusyError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=5) from exc

    payload = _run_payload(run, result, comparison)
    emit_result(
        "benchmark",
        data=payload,
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        status=run.status.value,
        message=result.message,
        task_id=str(run.task_id),
        experiment_id=run.id,
        human_lines=(
            f"Benchmark: {run.id}",
            f"Target: {run.target_kind} {run.target_id}",
            f"Status: {run.status.value}",
            *((f"Median: {result.summary.median:.9f}s",) if result.summary is not None else ()),
            *(
                (f"Improvement: {comparison.improvement_percent:.3f}%",)
                if comparison is not None
                else ()
            ),
        ),
    )
