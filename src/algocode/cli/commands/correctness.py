"""Run and replay correctness suites."""

from __future__ import annotations

import asyncio
import shlex
from base64 import b64encode
from pathlib import Path
from typing import Annotated, Any

import typer

from algocode.bootstrap import build_context
from algocode.cli.context import build_task_context
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.correctness.spec import load_correctness_spec
from algocode.correctness.types import CorrectnessResult
from algocode.domain.errors import ConfigError, CorrectnessError, NotFoundError
from algocode.domain.model import CorrectnessRun
from algocode.languages.types import BuildProfile

correctness_app = typer.Typer(
    name="correctness",
    help="Run or replay correctness suites.",
    no_args_is_help=True,
)

DataDirOption = Annotated[
    Path | None,
    typer.Option("--data-dir", help="Override the data directory."),
]
BuildCommandOption = Annotated[
    str | None,
    typer.Option("--build-command", help="Override the project build command."),
]
SourceRootOption = Annotated[
    str,
    typer.Option("--source-root", help="Source root relative to the workspace."),
]
TimeoutOption = Annotated[
    int,
    typer.Option("--timeout", min=1, help="Build timeout in seconds."),
]


def _run_payload(
    run: CorrectnessRun,
    result: CorrectnessResult,
) -> dict[str, Any]:
    return {
        "result_id": run.id,
        "task_id": str(run.task_id),
        "target_kind": run.target_kind,
        "target_id": run.target_id,
        "status": run.status.value,
        "failure_kind": run.failure_kind.value if run.failure_kind is not None else None,
        "spec_hash": run.spec_hash,
        "duration_seconds": result.duration_seconds,
        "passed_cases": result.passed_cases,
        "failed_cases": result.failed_cases,
        "message": result.message,
        "cases": [
            {
                "case_id": case.case_id,
                "passed": case.passed,
                "failure_kind": (
                    case.failure_kind.value if case.failure_kind is not None else None
                ),
                "message": case.message,
                "duration_seconds": case.duration_seconds,
                "actual_exit_code": case.actual_exit_code,
                "expected_exit_code": case.expected_exit_code,
                "seed": case.seed,
                "input_hash": case.input_hash,
                "generator_hash": case.generator_hash,
                "actual_output_base64": b64encode(case.actual_output).decode("ascii"),
                "expected_output_base64": (
                    b64encode(case.expected_output).decode("ascii")
                    if case.expected_output is not None
                    else None
                ),
                "actual_stderr_base64": b64encode(case.actual_stderr).decode("ascii"),
            }
            for case in result.cases
        ],
    }


@correctness_app.command("run")
def correctness_run(
    task_id: Annotated[str, typer.Argument(help="Task identifier.")],
    spec_path: Annotated[
        Path,
        typer.Option("--spec", help="Correctness specification YAML file."),
    ],
    build_command: BuildCommandOption = None,
    source_root: SourceRootOption = ".",
    timeout_seconds: TimeoutOption = 120,
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Run a correctness suite against the task baseline."""

    context = build_task_context(task_id, data_dir)
    profile = _build_profile(build_command, source_root, timeout_seconds)
    try:
        spec = load_correctness_spec(spec_path)
        run, result = asyncio.run(
            context.correctness_service.run_baseline(
                task_id,
                spec,
                build_profile=profile,
            )
        )
    except (ConfigError, CorrectnessError, NotFoundError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit_run("correctness.run", run, result, json_output, no_color, quiet, verbose)
    if not result.passed:
        raise typer.Exit(code=4)


@correctness_app.command("replay")
def correctness_replay(
    result_id: Annotated[str, typer.Argument(help="Stored correctness result identifier.")],
    build_command: BuildCommandOption = None,
    source_root: SourceRootOption = ".",
    timeout_seconds: TimeoutOption = 120,
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Replay a stored correctness result."""

    context = build_context(data_dir=data_dir)
    profile = _build_profile(build_command, source_root, timeout_seconds)
    try:
        run, result = asyncio.run(
            context.correctness_service.replay(result_id, build_profile=profile)
        )
    except (ConfigError, CorrectnessError, NotFoundError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit_run("correctness.replay", run, result, json_output, no_color, quiet, verbose)
    if not result.passed:
        raise typer.Exit(code=4)


def _emit_run(
    command: str,
    run: CorrectnessRun,
    result: CorrectnessResult,
    json_output: bool,
    no_color: bool,
    quiet: bool,
    verbose: bool,
) -> None:
    payload = _run_payload(run, result)
    emit_result(
        command,
        data=payload,
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        status=run.status.value,
        message=result.message,
        task_id=str(run.task_id),
        human_lines=(
            f"Correctness: {run.id}",
            f"Status: {run.status.value}",
            f"Passed cases: {result.passed_cases}",
            f"Failed cases: {result.failed_cases}",
            *((f"Failure: {result.failure_kind.value}",) if result.failure_kind else ()),
            *((f"Message: {result.message}",) if result.message else ()),
        ),
    )


def _build_profile(
    build_command: str | None,
    source_root: str,
    timeout_seconds: int,
) -> BuildProfile:
    commands: tuple[tuple[str, ...], ...] = ()
    if build_command:
        commands = (tuple(shlex.split(build_command)),)
    return BuildProfile(
        commands=commands,
        source_root=source_root,
        timeout_seconds=timeout_seconds,
    )
