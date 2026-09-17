"""Run the agent phase machine with a provider."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from algocode.application.services.project_state import (
    find_current_task,
    update_current_task,
)
from algocode.cli.context import build_task_context, resolve_data_dir
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.config import compute_config_hash
from algocode.domain.model import CorrectnessRun, TaskPhase, TaskStatus
from algocode.providers.errors import ProviderError
from algocode.providers.factory import build_provider, resolve_model_selection
from algocode.providers.fake import DeterministicFakeProvider
from algocode.providers.types import ModelRef
from algocode.runtime.agent import AgentRunResult, AgentRuntime

DataDirOption = Annotated[
    Path | None,
    typer.Option("--data-dir", help="Override the data directory."),
]


def _payload(result: AgentRunResult) -> dict[str, object]:
    return asdict(result)


def _candidate_correctness_state(
    candidate_id: str | None,
    correctness_runs: list[CorrectnessRun],
) -> dict[str, str | None] | None:
    if candidate_id is None:
        return None
    run = next(
        (
            item
            for item in correctness_runs
            if item.target_kind == "candidate" and item.target_id == candidate_id
        ),
        None,
    )
    return {
        "specPath": ".algocode/oracle/correctness.yaml",
        "resultId": str(run.id) if run is not None else None,
        "status": run.status.value if run is not None else None,
    }


def optimize_command(
    task_id: Annotated[
        str | None,
        typer.Argument(help="Task identifier. Defaults to .algocode/current-task.json."),
    ] = None,
    fake_provider: Annotated[
        bool,
        typer.Option("--fake-provider", help="Use the deterministic provider without API keys."),
    ] = False,
    provider_key: Annotated[
        str | None,
        typer.Option("--provider", help="Configured provider key. Defaults to project default."),
    ] = None,
    model_key: Annotated[
        str | None,
        typer.Option("--model", help="Configured model key. Defaults to project default."),
    ] = None,
    candidate_workspace: Annotated[
        Path | None,
        typer.Option("--candidate-workspace", help="Candidate worktree to operate on."),
    ] = None,
    candidate_id: Annotated[
        str | None,
        typer.Option("--candidate-id", help="Candidate identifier."),
    ] = None,
    max_steps: Annotated[
        int | None,
        typer.Option("--max-steps", min=1, help="Maximum model turns per phase."),
    ] = None,
    max_tool_calls: Annotated[
        int | None,
        typer.Option("--max-tool-calls", min=1, help="Maximum tool calls per phase."),
    ] = None,
    stop_after: Annotated[
        str,
        typer.Option("--stop-after", help="Stop after a named phase."),
    ] = TaskPhase.REPORT.value,
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
    command_name_override: Annotated[str, typer.Option("--command-name", hidden=True)] = "optimize",
) -> None:
    """Run the Agent Phase Machine and Tool Loop."""

    current_state = find_current_task(Path.cwd())
    if task_id is None:
        if current_state is None or not current_state.get("taskId"):
            typer.echo("no current task found; run algocode init or pass a task id", err=True)
            raise typer.Exit(code=2)
        task_id = str(current_state["taskId"])
    data_dir = resolve_data_dir(data_dir)

    try:
        stop_phase = TaskPhase(stop_after)
    except ValueError as exc:
        typer.echo(f"unknown phase: {stop_after}", err=True)
        raise typer.Exit(code=2) from exc

    context = build_task_context(task_id, data_dir)
    selected_provider, selected_model = resolve_model_selection(
        context.config, provider_key, model_key
    )
    if fake_provider:
        provider = DeterministicFakeProvider()
        model = ModelRef(provider_id="fake", model_id="deterministic")
    else:
        try:
            provider, model = build_provider(
                context.config,
                provider_key=selected_provider,
                model_key=selected_model,
            )
        except ProviderError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
    runtime = AgentRuntime(
        event_store=context.event_store,
        task_service=context.task_service,
        provider=provider,
        tool_registry=context.tool_registry,
        project_service=context.project_service,
        baseline_service=context.baseline_service,
        artifact_store=context.artifact_store,
        language_registry=context.language_registry,
        correctness_service=context.correctness_service,
        benchmark_service=context.benchmark_service,
        max_steps_per_phase=max_steps or context.config.runtime.max_steps_per_phase,
        max_tool_calls_per_phase=(
            max_tool_calls or context.config.runtime.max_tool_calls_per_phase
        ),
        protected_files=context.config.correctness.protected_files,
        database=context.database,
        candidate_service=context.candidate_service,
        resource_provider=context.resource_provider,
        redactor=context.secret_redactor,
        context_window=(
            context.config.models[selected_model].context_window
            if selected_model in context.config.models
            else 128_000
        ),
        config_hash=compute_config_hash(context.config),
        policy_hash=context.policy_engine.hash(),
        model=model,
        model_log_root=context.data_dir / "model-logs",
    )
    try:
        result = asyncio.run(
            runtime.run(
                task_id,
                candidate_workspace=candidate_workspace,
                candidate_id=candidate_id,
                stop_after=stop_phase,
                command_name=command_name_override,
            )
        )
    except ProviderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    payload = _payload(result)
    task = asyncio.run(context.task_service.get_task(result.task_id))
    project = asyncio.run(context.project_service.get(task.project_id))
    candidates = asyncio.run(context.candidate_service.list_for_task(result.task_id))
    benchmarks = asyncio.run(context.benchmark_service.list_for_task(result.task_id))
    correctness_runs = asyncio.run(context.correctness_service.list_for_task(result.task_id))
    candidate_id = str(candidates[0].id) if candidates else None
    correctness_state = _candidate_correctness_state(candidate_id, correctness_runs)
    candidate_benchmarks = [
        run
        for run in benchmarks
        if run.target_kind == "candidate" and run.comparison_ref is not None
    ]
    latest_benchmark = (
        candidate_benchmarks[-1]
        if candidate_benchmarks
        else (benchmarks[-1] if benchmarks else None)
    )
    experiment_id = str(latest_benchmark.id) if latest_benchmark is not None else None
    comparison = (
        asyncio.run(context.benchmark_service.read_comparison(latest_benchmark))
        if latest_benchmark is not None
        else None
    )
    next_command = (
        f"algocode retry {result.task_id}"
        if result.status != TaskStatus.COMPLETED.value
        else f"algocode report {result.task_id} --json"
    )
    update_current_task(
        project_root=project.root_path,
        status=result.status,
        summary=result.summary,
        currentPhase=task.current_phase.value,
        completedPhases=list(result.completed_phases),
        turns=result.turns,
        toolCalls=result.tool_calls,
        candidateId=candidate_id,
        experimentId=experiment_id,
        databasePath=str(context.database.path),
        **({"correctness": correctness_state} if correctness_state is not None else {}),
        benchmark={
            "specPath": ".algocode/benchmarks/benchmark.yaml",
            "runId": experiment_id,
            "valid": (bool(comparison.get("valid")) if isinstance(comparison, dict) else None),
            "improvementPercent": (
                float(comparison.get("improvement_percent", 0.0))
                if isinstance(comparison, dict)
                else None
            ),
        },
        nextCommand=next_command,
    )
    status = result.status
    emit_result(
        command_name_override,
        data=payload,
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        status=status,
        message=result.summary,
        task_id=result.task_id,
        candidate_id=candidate_id,
        human_lines=(
            f"Task: {result.task_id}",
            f"Status: {result.status}",
            f"Phases: {', '.join(result.completed_phases)}",
            f"Turns: {result.turns}",
            f"Tool calls: {result.tool_calls}",
        ),
    )
    if status != TaskStatus.COMPLETED.value:
        raise typer.Exit(code=1)
