"""Show the current task and candidate at a glance."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from algocode.application.services.project_state import find_current_task
from algocode.cli.context import resolve_task_candidate
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.domain.model import BenchmarkStatus, CorrectnessStatus, DecisionOutcome, TaskStatus

DataDirOption = Annotated[
    Path | None,
    typer.Option("--data-dir", help="Override the data directory."),
]


def status_command(
    task_id: Annotated[str | None, typer.Argument(help="Task identifier.")] = None,
    candidate_id: Annotated[
        str | None,
        typer.Option("--candidate-id", help="Candidate identifier."),
    ] = None,
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Show the current task, evidence, and recommended next command."""

    try:
        context, task, candidate = resolve_task_candidate(task_id, candidate_id, data_dir)
    except Exception as exc:  # noqa: BLE001
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    correctness_runs = asyncio.run(context.correctness_service.list_for_task(task.id))
    benchmark_runs = asyncio.run(context.benchmark_service.list_for_task(task.id))
    correctness = next(
        (
            run
            for run in correctness_runs
            if candidate is not None
            and run.target_kind == "candidate"
            and run.target_id == str(candidate.id)
        ),
        None,
    )
    benchmark = next(
        (
            run
            for run in benchmark_runs
            if candidate is not None
            and run.target_kind == "candidate"
            and run.target_id == str(candidate.id)
        ),
        None,
    )
    comparison = (
        asyncio.run(context.benchmark_service.read_comparison(benchmark))
        if benchmark is not None and benchmark.comparison_ref is not None
        else None
    )
    decision = (
        asyncio.run(context.decision_service.get_for_candidate(candidate.id))
        if candidate is not None
        else None
    )
    state = find_current_task(Path.cwd()) or {}
    next_command = _next_command(task.status, candidate, decision, correctness, benchmark)
    data = {
        "taskId": str(task.id),
        "projectId": str(task.project_id),
        "status": task.status.value,
        "currentPhase": task.current_phase.value,
        "completedPhases": state.get("completedPhases", []),
        "candidateId": str(candidate.id) if candidate is not None else None,
        "candidateStatus": candidate.status.value if candidate is not None else None,
        "correctness": {
            "resultId": correctness.id if correctness is not None else None,
            "status": correctness.status.value if correctness is not None else None,
        },
        "benchmark": {
            "runId": benchmark.id if benchmark is not None else None,
            "status": benchmark.status.value if benchmark is not None else None,
            "valid": comparison.get("valid") if comparison is not None else None,
            "improvementPercent": (
                comparison.get("improvement_percent") if comparison is not None else None
            ),
        },
        "decision": {
            "id": decision.id if decision is not None else None,
            "outcome": decision.outcome.value if decision is not None else None,
        },
        "nextCommand": next_command,
    }
    emit_result(
        "status",
        data=data,
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        status=task.status.value,
        task_id=str(task.id),
        candidate_id=str(candidate.id) if candidate is not None else None,
        human_lines=(
            f"Task: {task.id}",
            f"Status: {task.status.value}",
            f"Phase: {task.current_phase.value}",
            f"Candidate: {candidate.id if candidate is not None else 'none'}",
            f"Candidate status: {candidate.status.value if candidate is not None else '-'}",
            f"Correctness: {correctness.status.value if correctness is not None else 'not run'}",
            f"Benchmark: {(comparison or {}).get('improvement_percent', 'not run')}",
            f"Next: {next_command}",
        ),
    )


def _next_command(task_status, candidate, decision, correctness, benchmark) -> str:
    if task_status is not TaskStatus.COMPLETED:
        return "algocode optimize"
    if candidate is None:
        return "algocode optimize"
    if correctness is not None and correctness.status is not CorrectnessStatus.PASSED:
        return "algocode optimize"
    if benchmark is not None and benchmark.status is not BenchmarkStatus.COMPLETED:
        return "algocode optimize"
    if decision is not None and decision.outcome is DecisionOutcome.ACCEPTED:
        return "algocode apply"
    return "algocode review"
