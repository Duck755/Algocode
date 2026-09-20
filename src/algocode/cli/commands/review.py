"""Present a complete evidence review for the current candidate."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from algocode.cli.context import resolve_task_candidate
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.workspace import GitRepository

DataDirOption = Annotated[
    Path | None,
    typer.Option("--data-dir", help="Override the data directory."),
]


def review_command(
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
    """Review correctness, benchmark, decision, and candidate changes."""

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
    changed_files: list[str] = []
    if candidate is not None:
        repository = asyncio.run(GitRepository.discover(candidate.workspace_ref))
        changed_files = list(asyncio.run(repository.changed_files(Path(candidate.workspace_ref))))

    data = {
        "task": {
            "id": str(task.id),
            "objective": task.objective,
            "status": task.status.value,
            "currentPhase": task.current_phase.value,
        },
        "candidate": (
            {
                "id": str(candidate.id),
                "status": candidate.status.value,
                "workspace": candidate.workspace_ref,
                "changedFiles": changed_files,
            }
            if candidate is not None
            else None
        ),
        "correctness": (
            {
                "resultId": correctness.id,
                "status": correctness.status.value,
                "failureKind": (
                    correctness.failure_kind.value if correctness.failure_kind is not None else None
                ),
            }
            if correctness is not None
            else None
        ),
        "benchmark": (
            {
                "runId": benchmark.id,
                "status": benchmark.status.value,
                "comparison": comparison,
            }
            if benchmark is not None
            else None
        ),
        "decision": (
            {
                "id": str(decision.id),
                "outcome": decision.outcome.value,
                "reason": decision.reason,
            }
            if decision is not None
            else None
        ),
    }
    benchmark_lines = ()
    if comparison is not None:
        benchmark_lines = (
            f"Baseline median: {comparison.get('baseline_median')}",
            f"Candidate median: {comparison.get('candidate_median')}",
            f"Improvement: {comparison.get('improvement_percent')}%",
            f"Benchmark valid: {comparison.get('valid')}",
        )
        if comparison.get("ci_lower") is not None and comparison.get("ci_upper") is not None:
            benchmark_lines += (
                f"Improvement CI: [{comparison.get('ci_lower')}, {comparison.get('ci_upper')}]",
            )
    emit_result(
        "review",
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
            f"Objective: {task.objective}",
            f"Status: {task.status.value}",
            f"Candidate: {candidate.id if candidate is not None else 'none'}",
            f"Candidate status: {candidate.status.value if candidate is not None else '-'}",
            f"Changed files: {', '.join(changed_files) if changed_files else 'none'}",
            f"Correctness: {correctness.status.value if correctness is not None else 'not run'}",
            *benchmark_lines,
            f"Decision: {decision.outcome.value if decision is not None else 'not made'}",
        ),
    )
