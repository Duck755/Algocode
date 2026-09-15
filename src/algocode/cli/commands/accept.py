"""Accept a verified candidate without modifying the workspace."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any

import typer

from algocode.cli.context import build_task_context
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.domain.errors import DecisionError
from algocode.domain.model import Decision

DataDirOption = Annotated[
    Path | None,
    typer.Option("--data-dir", help="Override the data directory."),
]


def _payload(decision: Decision) -> dict[str, Any]:
    payload = asdict(decision)
    payload["outcome"] = decision.outcome.value
    payload["decided_at"] = decision.decided_at.isoformat()
    return payload


def accept_command(
    task_id: Annotated[str, typer.Argument(help="Task identifier.")],
    candidate_id: Annotated[str, typer.Argument(help="Candidate identifier.")],
    reason: Annotated[
        str,
        typer.Option("--reason", help="Decision rationale."),
    ] = "",
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Record an accepted decision without applying the candidate."""

    try:
        decision = asyncio.run(
            build_task_context(task_id, data_dir).decision_service.accept(
                task_id,
                candidate_id,
                reason=reason,
            )
        )
    except DecisionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    payload = _payload(decision)
    emit_result(
        "accept",
        data=payload,
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        status=decision.outcome.value,
        task_id=task_id,
        candidate_id=candidate_id,
        human_lines=(
            f"Decision: {decision.id}",
            f"Outcome: {decision.outcome.value}",
            f"Reason: {decision.reason}",
        ),
    )
