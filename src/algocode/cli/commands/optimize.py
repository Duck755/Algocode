"""Run the agent phase machine with a provider."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from algocode.cli.context import build_task_context
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.config import compute_config_hash
from algocode.domain.model import TaskPhase, TaskStatus
from algocode.providers.errors import ProviderError
from algocode.providers.factory import build_provider
from algocode.providers.fake import DeterministicFakeProvider
from algocode.providers.types import ModelRef
from algocode.runtime.agent import AgentRunResult, AgentRuntime

DataDirOption = Annotated[
    Path | None,
    typer.Option("--data-dir", help="Override the data directory."),
]


def _payload(result: AgentRunResult) -> dict[str, object]:
    return asdict(result)


def optimize_command(
    task_id: Annotated[str, typer.Argument(help="Task identifier.")],
    fake_provider: Annotated[
        bool,
        typer.Option("--fake-provider", help="Use the deterministic provider without API keys."),
    ] = False,
    provider_key: Annotated[
        str,
        typer.Option("--provider", help="Configured provider key."),
    ] = "default",
    model_key: Annotated[
        str,
        typer.Option("--model", help="Configured model key."),
    ] = "default",
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
) -> None:
    """Run the Agent Phase Machine and Tool Loop."""

    try:
        stop_phase = TaskPhase(stop_after)
    except ValueError as exc:
        typer.echo(f"unknown phase: {stop_after}", err=True)
        raise typer.Exit(code=2) from exc

    context = build_task_context(task_id, data_dir)
    if fake_provider:
        provider = DeterministicFakeProvider()
        model = ModelRef(provider_id="fake", model_id="deterministic")
    else:
        try:
            provider, model = build_provider(
                context.config,
                provider_key=provider_key,
                model_key=model_key,
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
            context.config.models[model_key].context_window
            if model_key in context.config.models
            else 128_000
        ),
        config_hash=compute_config_hash(context.config),
        policy_hash=context.policy_engine.hash(),
        model=model,
    )
    try:
        result = asyncio.run(
            runtime.run(
                task_id,
                candidate_workspace=candidate_workspace,
                candidate_id=candidate_id,
                stop_after=stop_phase,
            )
        )
    except ProviderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    payload = _payload(result)
    status = result.status
    emit_result(
        "optimize",
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
