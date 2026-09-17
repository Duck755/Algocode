"""Initialize and register a local project."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any

import typer

from algocode.application.services.project_bootstrap_service import (
    ProjectBootstrapService,
    bootstrap_payload,
)
from algocode.bootstrap import build_context
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.domain.errors import ConfigError
from algocode.domain.model import Project
from algocode.workspace.git import GitError

DataDirOption = Annotated[
    Path | None,
    typer.Option("--data-dir", help="Override the data directory."),
]


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
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Detect and register the project without modifying its source files."""

    try:
        context = build_context(project_root=path, data_dir=data_dir)
        if bootstrap:
            result = asyncio.run(
                ProjectBootstrapService(context).run(
                    path,
                    language=language,
                    objective=objective,
                )
            )
            payload = bootstrap_payload(result)
            project = result.project
            emit_result(
                "init",
                data=payload,
                json_output=json_output,
                no_color=no_color,
                quiet=quiet,
                verbose=verbose,
                task_id=str(result.task.id),
                human_lines=(
                    f"Project: {result.project.id}",
                    f"Root: {result.project.root_path}",
                    f"Language: {result.project.language.value}",
                    f"Git initialized: {result.git_initialized}",
                    f"Initial commit created: {result.commit_created}",
                    f"Bootstrap: {result.bootstrap_status}",
                    f"Task: {result.task.id}",
                    f"Baseline: {result.baseline.id}",
                    f"Correctness: {getattr(result.correctness, 'status', 'not run')}",
                    f"Benchmark: {getattr(result.benchmark_run, 'status', 'not run')}",
                    f"Next: algocode optimize {result.task.id} --provider default --model default",
                ),
            )
            return

        project = asyncio.run(
            context.project_service.register(
                path,
                language=language,
                write_config=write_config,
            )
        )
    except (ConfigError, GitError, ValueError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

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
