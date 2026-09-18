"""Generate task reports."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from algocode.cli.context import build_task_context
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result

DataDirOption = Annotated[
    Path | None,
    typer.Option("--data-dir", help="Override the data directory."),
]


def report_command(
    task_id: Annotated[str, typer.Argument(help="Task identifier.")],
    markdown: Annotated[
        bool,
        typer.Option("--markdown", help="Emit Markdown instead of canonical JSON."),
    ] = False,
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Generate and persist a task report."""

    if markdown and json_output:
        typer.echo("--markdown and --json cannot be used together", err=True)
        raise typer.Exit(code=2)
    payload, markdown_text, refs = asyncio.run(
        build_task_context(task_id, data_dir).report_service.build(task_id)
    )
    if markdown:
        typer.echo(markdown_text)
        return
    emit_result(
        "report",
        data=payload,
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        task_id=task_id,
        artifacts=(refs["json_ref"], refs["markdown_ref"]),
        human_lines=(
            f"Report: {payload['reportId']}",
            f"Task: {payload['taskId']}",
            f"Status: {payload['finalStatus']}",
            f"JSON artifact: {refs['json_ref']['uri']}",
            f"Markdown artifact: {refs['markdown_ref']['uri']}",
            f"Markdown report: {refs['root_markdown_path']}",
        ),
    )
