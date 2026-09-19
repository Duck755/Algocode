"""Run the agent phase machine with a provider."""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from algocode.application.services.project_state import (
    find_current_task,
    update_current_task,
)
from algocode.cli.context import build_task_context, resolve_data_dir
from algocode.cli.live_progress import LiveProgress, phase_label, poll_events
from algocode.cli.output import (
    JsonOption,
    NoColorOption,
    ProgressOption,
    QuietOption,
    VerboseOption,
    emit_result,
    is_interactive,
)
from algocode.cli.progress import format_duration, render_evidence
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


def _short(value: object) -> str:
    text = str(value)
    return text[:8] if len(text) > 8 else text


def _trim(text: str, limit: int = 96) -> str:
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def _evidence_rows(
    *,
    result: AgentRunResult,
    candidate: object | None,
    correctness_state: dict[str, str | None] | None,
    benchmark: object | None,
    comparison: dict[str, object] | None,
    decision: object | None,
    elapsed: float,
) -> list[tuple[str, str, str]]:
    """Assemble the evidence block printed after a run."""

    rows: list[tuple[str, str, str]] = [
        ("任务", f"task:{_short(result.task_id)}", result.status),
        (
            "耗时",
            format_duration(elapsed),
            f"{result.turns} 轮推理 · {result.tool_calls} 次工具调用",
        ),
        (
            "阶段",
            f"{len(result.completed_phases)} 个",
            " → ".join(phase_label(name) for name in result.completed_phases) or "-",
        ),
    ]
    if candidate is None:
        rows.append(("候选", "未创建", "本次运行未产生候选"))
    else:
        rows.append(("候选", f"candidate:{_short(candidate.id)}", str(candidate.status)))
    if correctness_state is None or correctness_state.get("resultId") is None:
        rows.append(("正确性", "未运行", "缺少候选正确性结果"))
    else:
        rows.append(
            (
                "正确性",
                f"run:{_short(correctness_state['resultId'])}",
                str(correctness_state.get("status") or "-"),
            )
        )
    if benchmark is None:
        rows.append(("基准", "未运行", "缺少候选基准结果"))
    else:
        valid = comparison.get("valid") if isinstance(comparison, dict) else None
        rows.append(("基准", f"benchmark:{_short(benchmark.id)}", f"valid={valid}"))
    if isinstance(comparison, dict) and comparison.get("improvement_percent") is not None:
        note = (
            f"{float(comparison.get('baseline_median', 0.0)):.3f}"
            f" → {float(comparison.get('candidate_median', 0.0)):.3f}"
            f" · p={float(comparison.get('p_value', 1.0)):.3f}"
        )
        rows.append(("提升", f"{float(comparison['improvement_percent']):+.2f}%", note))
    if decision is not None:
        rows.append(
            (
                "决策",
                str(decision.outcome),
                _trim(str(decision.reason or "-")),
            )
        )
    return rows


def _offer_next_steps(
    *,
    task_id: str,
    candidate_id: str | None,
    accepted: bool,
    data_dir: Path | None,
) -> None:
    """Offer the follow-up commands an operator is most likely to want."""

    options: list[tuple[str, str]] = []
    if candidate_id is not None:
        options.append(("查看候选改动", f"algocode diff {task_id}"))
        if accepted:
            options.append(("应用候选", f"algocode apply {task_id}"))
    options.append(("生成任务报告", f"algocode report {task_id} --markdown"))
    options.append(("重新规划重试", f"algocode retry {task_id}"))
    typer.echo("")
    typer.echo("下一步：")
    for index, (label, command) in enumerate(options, start=1):
        typer.echo(f"  {index}) {label}  ({command})")
    try:
        answer = typer.prompt(
            f"选择 [1/{len(options)}，回车退出]",
            default="",
            show_default=False,
        )
    except (typer.Abort, EOFError):
        return
    choice = answer.strip()
    if not choice.isdigit() or not 1 <= int(choice) <= len(options):
        return
    selected = options[int(choice) - 1][0]
    try:
        if selected == "查看候选改动":
            from algocode.cli.commands.diff import diff_command

            diff_command(task_id, candidate_id=candidate_id, data_dir=data_dir)
        elif selected == "应用候选":
            from algocode.cli.commands.apply import apply_command

            apply_command(task_id, candidate_id, data_dir=data_dir)
        elif selected == "生成任务报告":
            from algocode.cli.commands.report import report_command

            report_command(task_id, markdown=True, data_dir=data_dir)
        else:
            from algocode.cli.commands.retry import retry_command

            retry_command(task_id, data_dir=data_dir)
    except typer.Exit:
        return


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
    progress: ProgressOption = None,
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
        decision_service=context.decision_service,
        experiment_service=context.experiment_service,
        search_archive_service=context.search_archive_service,
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
        max_candidates=context.config.runtime.max_candidates,
        max_population=context.config.runtime.max_population,
        max_evals=context.config.runtime.max_evals,
        max_iterations=context.config.runtime.max_iterations,
        cost_budget_usd=context.config.runtime.cost_budget_usd,
    )
    live = LiveProgress(
        load_events=poll_events(context.event_store, str(task_id)),
        enabled=(not quiet and not json_output) if progress is None else bool(progress),
        color=not no_color,
    )
    started_at = time.perf_counter()
    live.start()
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
        live.close(ok=False)
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except KeyboardInterrupt as exc:
        live.close(ok=False)
        typer.echo(
            "已中断；可执行 algocode retry 继续本次任务",
            err=True,
        )
        raise typer.Exit(code=130) from exc
    elapsed = time.perf_counter() - started_at
    live.close(ok=result.status == TaskStatus.COMPLETED.value)

    payload = _payload(result)
    task = asyncio.run(context.task_service.get_task(result.task_id))
    project = asyncio.run(context.project_service.get(task.project_id))
    candidates = asyncio.run(context.candidate_service.list_for_task(result.task_id))
    benchmarks = asyncio.run(context.benchmark_service.list_for_task(result.task_id))
    correctness_runs = asyncio.run(context.correctness_service.list_for_task(result.task_id))
    candidate = candidates[0] if candidates else None
    candidate_id = str(candidate.id) if candidate is not None else None
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
        taskId=result.task_id,
        projectId=str(project.id),
        language=project.language.value,
        gitRevision=str(project.git_revision),
        objective=task.objective,
        dataDir=str(context.data_dir.expanduser().resolve()),
        status=result.status,
        summary=result.summary,
        currentPhase=task.current_phase.value,
        completedPhases=list(result.completed_phases),
        turns=result.turns,
        toolCalls=result.tool_calls,
        candidateId=candidate_id,
        experimentId=experiment_id,
        databasePath=str(context.database.path.expanduser().resolve()),
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
    decision = (
        asyncio.run(context.decision_service.get_for_candidate(candidate_id))
        if candidate_id is not None
        else None
    )
    rows = _evidence_rows(
        result=result,
        candidate=candidate,
        correctness_state=correctness_state,
        benchmark=latest_benchmark,
        comparison=comparison,
        decision=decision,
        elapsed=elapsed,
    )
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
            f"{command_name_override} · {status} · 耗时 {format_duration(elapsed)}",
            *render_evidence(rows),
        ),
    )
    if is_interactive() and not json_output and not quiet:
        _offer_next_steps(
            task_id=result.task_id,
            candidate_id=candidate_id,
            accepted=decision is not None and str(decision.outcome) == "accepted",
            data_dir=data_dir,
        )
    if status != TaskStatus.COMPLETED.value:
        raise typer.Exit(code=1)
