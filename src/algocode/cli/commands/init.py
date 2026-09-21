"""Initialize and register a local project."""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any

import typer

from algocode.application.services.project_bootstrap_service import (
    BootstrapEvent,
    BootstrapResult,
    ProjectBootstrapService,
    bootstrap_payload,
)
from algocode.bootstrap import build_context
from algocode.cli.output import (
    JsonOption,
    NoColorOption,
    ProgressOption,
    QuietOption,
    VerboseOption,
    YesOption,
    emit_result,
    is_interactive,
)
from algocode.cli.progress import StageReporter, format_duration, render_evidence
from algocode.domain.errors import ConfigError
from algocode.domain.model import Project
from algocode.providers.errors import ProviderError
from algocode.providers.factory import build_provider
from algocode.workspace.git import GitError

DataDirOption = Annotated[
    Path | None,
    typer.Option("--data-dir", help="Override the data directory."),
]

INIT_STAGES = ("SCAN", "CONTRACT", "SPECS", "BASELINE", "CORRECTNESS", "BENCHMARK", "READY")
_STAGE_LABELS = {
    "scan": "SCAN",
    "contract": "CONTRACT",
    "specs": "SPECS",
    "baseline": "BASELINE",
    "correctness": "CORRECTNESS",
    "benchmark": "BENCHMARK",
    "persist": "READY",
}


class _RailAdapter:
    """Translate bootstrap events into stage-rail calls."""

    def __init__(self, reporter: StageReporter) -> None:
        self._reporter = reporter
        self._active: str | None = None

    def __call__(self, event: BootstrapEvent) -> None:
        label = _STAGE_LABELS.get(event.stage)
        if label is None:
            return
        if event.kind == "start":
            self._reporter.begin(label, event.detail)
            self._active = label
        elif event.kind == "detail":
            if label == self._active:
                self._reporter.update(event.detail)
        elif event.kind == "finish":
            self._reporter.complete(label, event.detail)
            if label == self._active:
                self._active = None
        elif event.kind == "fail":
            self._reporter.fail(event.detail or f"{label} failed")
            self._active = None
        elif event.kind == "note":
            self._reporter.note(event.detail)


def _reporter(
    progress: bool | None,
    *,
    quiet: bool,
    json_output: bool,
    no_color: bool,
) -> StageReporter:
    enabled = (not quiet and not json_output) if progress is None else progress
    return StageReporter(
        INIT_STAGES,
        title="algocode · init",
        enabled=enabled,
        color=not no_color,
    )


def _preflight_lines(context, root: Path, language: str) -> list[str]:
    detected = asyncio.run(context.language_registry.detect(root))
    resolved = context.language_registry.resolve_language(language, detected)
    try:
        build_provider(context.config)
        model_note = f"{context.config.defaults.provider}/{context.config.defaults.model}"
    except ProviderError:
        model_note = "not configured (deterministic fallback contract will be used)"
    git_note = "already initialized" if (root / ".git").exists() else "will run git init"
    return [
        f"Project directory: {root}",
        f"Language: {resolved.value}",
        f"Git: {git_note}",
        f"Model: {model_note}",
        "Creates configuration, contract, tests, benchmark, and task state under .algocode/",
        "Tip: use --no-bootstrap to register only and skip artifact generation",
    ]


def _confirm(lines: list[str]) -> bool:
    for line in lines:
        typer.echo(f"  {line}")
    typer.echo("")
    try:
        answer = typer.prompt("Continue? [Y/n]", default="y", show_default=False)
    except (typer.Abort, EOFError):
        return False
    return answer.strip().lower() in {"", "y", "yes"}


def _short(value: object) -> str:
    text = str(value)
    return text[:8] if len(text) > 8 else text


def _median_note(summary: object, samples: int) -> str:
    """Report the measured median next to the sample count.

    The count alone hides whether the benchmark is even in a range worth
    comparing, so show the number the comparison is actually built on.
    """

    median = getattr(summary, "median", None)
    if median is None:
        return f"{samples} samples"
    return f"{format_duration(float(median))} · {samples} samples"


def _evidence_rows(result: BootstrapResult, seed: int) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    contract_name = Path(result.contract_path).name if result.contract_path else "contract.json"
    if result.contract_confidence is not None:
        contract_note = f"confidence {result.contract_confidence:.2f}"
    else:
        contract_note = result.contract_source or "-"
    if result.contract_source == "deterministic-fallback":
        contract_note += " · fallback"
    rows.append(("Contract", f".algocode/{contract_name}", contract_note))
    rows.append(
        (
            "Baseline",
            f"baseline:{_short(result.baseline.id)}",
            f"git {str(result.project.git_revision)[:7]} · seed {seed}",
        )
    )
    if result.correctness is not None:
        total = len(result.correctness.cases)
        rows.append(
            (
                "Correctness",
                f"correctness:{_short(result.correctness_run_id or '-')}",
                f"{result.correctness.passed_cases}/{total} passed",
            )
        )
    else:
        rows.append(("Correctness", "skipped", "correctness specification was not generated"))
    if result.benchmark_run is not None and result.benchmark_result is not None:
        summary = result.benchmark_result.summary
        samples = summary.count if summary is not None else len(result.benchmark_result.samples)
        rows.append(
            (
                "Benchmark",
                f"benchmark:{_short(result.benchmark_run.id)}",
                f"valid · {_median_note(summary, samples)}",
            )
        )
    else:
        rows.append(("Benchmark", "skipped", "benchmark specification was not generated"))
    rows.append(("Task", f"task:{_short(result.task.id)}", "ready"))
    return rows


def _failure_hint(exc: Exception) -> str:
    message = str(exc)
    if "entrypoint" in message:
        return "Add test.py/main.py or test.cpp/main.cpp at the project root, or use --no-bootstrap"
    if "contract test failed" in message:
        return "Inspect the contract test under .algocode/oracle/, or use --no-bootstrap to skip it"
    if "correctness specification failed" in message:
        return "Check .algocode/oracle/correctness.yaml against the project output"
    if "benchmark specification failed" in message:
        return "Check .algocode/benchmarks/benchmark.yaml"
    return ""


def _offer_next_steps(result: BootstrapResult, data_dir: Path | None) -> None:
    task_id = str(result.task.id)
    options = (
        ("Start optimization", f"algocode optimize {task_id}"),
        ("View baseline report", f"algocode report {task_id} --markdown"),
        ("Configure model", "algocode api"),
    )
    typer.echo("")
    typer.echo("Next steps:")
    for index, (label, command) in enumerate(options, start=1):
        typer.echo(f"  {index}) {label}  ({command})")
    try:
        answer = typer.prompt("Choose [1/2/3, Enter to exit]", default="", show_default=False)
    except (typer.Abort, EOFError):
        return
    choice = answer.strip()
    if choice not in {"1", "2", "3"}:
        return
    try:
        if choice == "1":
            from algocode.cli.commands.optimize import optimize_command

            optimize_command(task_id=task_id, data_dir=data_dir)
        elif choice == "2":
            from algocode.cli.commands.report import report_command

            report_command(task_id=task_id, markdown=True, data_dir=data_dir)
        else:
            from algocode.cli.commands.api import api_command

            api_command()
    except typer.Exit:
        return


def _project_payload(project: Project) -> dict[str, Any]:
    payload = asdict(project)
    payload["language"] = project.language.value
    payload["created_at"] = project.created_at.isoformat()
    payload["updated_at"] = project.updated_at.isoformat()
    return payload


def init_command(
    path: Annotated[
        Path,
        typer.Option("--path", help="Project directory inside a Git repository."),
    ] = Path("."),
    language: Annotated[
        str,
        typer.Option("--language", help="auto, cpp, or python."),
    ] = "auto",
    objective: Annotated[
        str | None,
        typer.Option("--objective", help="Optimization objective for the initial task."),
    ] = None,
    bootstrap: Annotated[
        bool,
        typer.Option(
            "--bootstrap/--no-bootstrap",
            help="Create Git/config prerequisites and run the first baseline.",
        ),
    ] = True,
    write_config: Annotated[
        bool,
        typer.Option(
            "--write-config/--no-write-config",
            help="Create .algocode/config.yaml.",
        ),
    ] = True,
    progress: ProgressOption = None,
    yes: YesOption = False,
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Detect and register the project without modifying its source files."""

    interactive = is_interactive()
    reporter = _reporter(
        progress,
        quiet=quiet,
        json_output=json_output,
        no_color=no_color,
    )
    try:
        context = build_context(project_root=path, data_dir=data_dir)
        if bootstrap:
            root = Path(path).expanduser().resolve()
            if interactive and not yes and not json_output and not quiet:
                if not _confirm(_preflight_lines(context, root, language)):
                    typer.echo("Cancelled.")
                    raise typer.Exit(code=0)
            started_at = time.perf_counter()
            result = asyncio.run(
                ProjectBootstrapService(context).run(
                    path,
                    language=language,
                    objective=objective,
                    on_event=_RailAdapter(reporter),
                )
            )
            elapsed = time.perf_counter() - started_at
            reporter.close()
            payload = bootstrap_payload(result)
            rows = _evidence_rows(result, seed=context.config.runtime.run_seed)
            human_lines = [
                f"init completed · elapsed {format_duration(elapsed)}",
                *render_evidence(rows),
            ]
            emit_result(
                "init",
                data=payload,
                json_output=json_output,
                no_color=no_color,
                quiet=quiet,
                verbose=verbose,
                task_id=str(result.task.id),
                human_lines=human_lines,
            )
            if interactive and not json_output and not quiet:
                _offer_next_steps(result, data_dir)
            return

        project = asyncio.run(
            context.project_service.register(
                path,
                language=language,
                write_config=write_config,
            )
        )
    except (ConfigError, GitError, ValueError, RuntimeError) as exc:
        reporter.fail(str(exc), hint=_failure_hint(exc))
        reporter.close()
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    finally:
        reporter.close()

    payload = _project_payload(project)
    emit_result(
        "init",
        data=payload,
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        human_lines=(
            f"Project: {project.id}",
            f"Root: {project.root_path}",
            f"Language: {project.language.value}",
            f"Revision: {project.git_revision}",
            f"Data directory: {context.data_dir}",
        ),
    )
