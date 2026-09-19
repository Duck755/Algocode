"""Cleanup command for local caches and expired artifacts."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from algocode.bootstrap import build_context
from algocode.cli.context import resolve_data_dir
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result


def gc_command(
    include_worktrees: Annotated[
        bool,
        typer.Option(
            "--include-worktrees",
            help="Also remove expired candidate and baseline worktrees.",
        ),
    ] = False,
    data_dir: Annotated[
        Path | None,
        typer.Option("--data-dir", help="Override the data directory."),
    ] = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Remove local artifacts and logs older than the configured retention period."""

    resolved_data_dir = resolve_data_dir(data_dir)
    context = build_context(data_dir=resolved_data_dir)
    result = asyncio.run(
        context.maintenance_service.cleanup(include_worktrees=include_worktrees)
    )
    payload = {
        "retentionDays": result.retention_days,
        "removedFiles": list(result.removed_files),
        "removedBytes": result.removed_bytes,
        "skippedFiles": list(result.skipped_files),
    }
    human_lines = (
        f"Retention: {result.retention_days} days",
        f"Removed files: {len(result.removed_files)}",
        f"Removed bytes: {result.removed_bytes}",
    )
    emit_result(
        "gc",
        data=payload,
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        status="completed",
        message=f"removed {len(result.removed_files)} files",
        human_lines=human_lines,
    )
