"""Show the current task and candidate at a glance."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from algocode.application.services.project_state import find_current_task
from algocode.cli.context import resolve_task_candidate
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.domain.events import EventEnvelope, EventType
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
    events = asyncio.run(context.event_store.read(task.id))
    progress = _build_progress(
        events,
        task.current_phase.value,
        active=task.status is TaskStatus.RUNNING,
    )
    next_command = _next_command(task.status, candidate, decision, correctness, benchmark)
    data = {
        "taskId": str(task.id),
        "projectId": str(task.project_id),
        "status": task.status.value,
        "currentPhase": task.current_phase.value,
        "progress": progress,
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
            f"Progress: {_progress_line(progress)}",
            f"Candidate: {candidate.id if candidate is not None else 'none'}",
            f"Candidate status: {candidate.status.value if candidate is not None else '-'}",
            f"Correctness: {correctness.status.value if correctness is not None else 'not run'}",
            f"Benchmark: {(comparison or {}).get('improvement_percent', 'not run')}",
            f"Next: {next_command}",
        ),
    )


def _build_progress(
    events: Sequence[EventEnvelope],
    current_phase,
    *,
    now: datetime | None = None,
    active: bool = True,
) -> dict[str, object]:
    phase = getattr(current_phase, "value", str(current_phase))
    ordered = sorted(events, key=lambda event: event.seq)
    current_time = now or datetime.now(UTC)
    if not active and ordered:
        current_time = ordered[-1].timestamp
    empty = {
        "phase": phase,
        "phaseStartedAt": None,
        "phaseElapsedSeconds": None,
        "turn": None,
        "toolCalls": 0,
        "activeTool": None,
        "lastTool": None,
        "lastEvent": None,
        "lastEventAt": None,
        "lastEventSummary": "waiting",
    }
    if not ordered:
        return empty

    phase_events = [event for event in ordered if event.payload.get("phase") == phase]
    phase_changes = [
        event
        for event in ordered
        if event.type is EventType.TASK_PHASE_CHANGED
        and event.payload.get("current_phase") == phase
    ]
    phase_started = phase_changes[-1].timestamp if phase_changes else None

    turn = None
    for event in reversed(phase_events):
        if event.type is EventType.AGENT_TURN_STARTED:
            value = event.payload.get("turn")
            turn = value if isinstance(value, int) else None
            break

    tool_started = [
        event for event in phase_events if event.type is EventType.TOOL_CALL_STARTED
    ]
    completed_ids = {
        event.payload.get("tool_call_id")
        for event in phase_events
        if event.type is EventType.TOOL_CALL_COMPLETED
    }
    active_tool_event = next(
        (
            event
            for event in reversed(tool_started)
            if event.payload.get("tool_call_id") not in completed_ids
        ),
        None,
    )
    last_tool_event = next(
        (
            event
            for event in reversed(phase_events)
            if event.type is EventType.TOOL_CALL_COMPLETED
        ),
        None,
    )
    last_event = ordered[-1]
    phase_elapsed = (
        max(0.0, (current_time - phase_started).total_seconds())
        if phase_started is not None
        else None
    )
    return {
        **empty,
        "phaseStartedAt": phase_started.isoformat() if phase_started else None,
        "phaseElapsedSeconds": (
            round(phase_elapsed, 1) if phase_elapsed is not None else None
        ),
        "turn": turn,
        "toolCalls": len(tool_started),
        "activeTool": (
            _active_tool_payload(active_tool_event, current_time)
            if active_tool_event is not None
            else None
        ),
        "lastTool": (
            _completed_tool_payload(last_tool_event)
            if last_tool_event is not None
            else None
        ),
        "lastEvent": last_event.type.value,
        "lastEventAt": last_event.timestamp.isoformat(),
        "lastEventSummary": _event_summary(last_event),
    }


def _active_tool_payload(event: EventEnvelope, now: datetime) -> dict[str, object]:
    return {
        "name": event.payload.get("name") or "unknown",
        "startedAt": event.timestamp.isoformat(),
        "elapsedSeconds": round(
            max(0.0, (now - event.timestamp).total_seconds()),
            1,
        ),
    }


def _completed_tool_payload(event: EventEnvelope) -> dict[str, object]:
    summary = str(event.payload.get("summary") or "")
    return {
        "name": event.payload.get("name") or "unknown",
        "status": event.payload.get("status") or "unknown",
        "summary": summary[:160],
        "completedAt": event.timestamp.isoformat(),
    }


def _event_summary(event: EventEnvelope) -> str:
    labels = {
        EventType.BASELINE_STARTED: "capturing baseline",
        EventType.BASELINE_CAPTURED: "baseline captured",
        EventType.BASELINE_FAILED: "baseline failed",
        EventType.BUILD_STARTED: "building candidate",
        EventType.BUILD_SUCCEEDED: "candidate build completed",
        EventType.BUILD_FAILED: "candidate build failed",
        EventType.CORRECTNESS_STARTED: "running correctness",
        EventType.CORRECTNESS_PASSED: "correctness passed",
        EventType.CORRECTNESS_FAILED: "correctness failed",
        EventType.EXPERIMENT_STARTED: "running benchmark",
        EventType.EXPERIMENT_COMPLETED: "benchmark completed",
        EventType.EXPERIMENT_FAILED: "benchmark failed",
        EventType.COMPARISON_PRODUCED: "comparison produced",
        EventType.DECISION_MADE: "decision made",
        EventType.REPORT_GENERATED: "report generated",
    }
    if event.type in labels:
        return labels[event.type]
    if event.type is EventType.AGENT_TURN_STARTED:
        return f"agent turn {event.payload.get('turn')}"
    if event.type is EventType.AGENT_TURN_COMPLETED:
        return "agent turn completed"
    if event.type is EventType.TOOL_CALL_STARTED:
        return f"running {event.payload.get('name') or 'tool'}"
    if event.type is EventType.TOOL_CALL_COMPLETED:
        name = event.payload.get("name") or "tool"
        status = event.payload.get("status") or "completed"
        summary = str(event.payload.get("summary") or "").strip()
        return f"{name} {status}" + (f": {summary[:120]}" if summary else "")
    return event.type.value.replace(".", " ")


def _progress_line(progress: dict[str, object]) -> str:
    parts = [str(progress.get("phase") or "unknown")]
    turn = progress.get("turn")
    if isinstance(turn, int):
        parts.append(f"turn {turn}")
    active = progress.get("activeTool")
    if isinstance(active, dict):
        parts.append(
            f"tool={active.get('name')} ({active.get('elapsedSeconds', 0)}s)"
        )
    else:
        last_tool = progress.get("lastTool")
        if isinstance(last_tool, dict):
            parts.append(f"last={last_tool.get('name')} {last_tool.get('status')}")
        else:
            last_event = progress.get("lastEventSummary")
            if last_event:
                parts.append(str(last_event))
    elapsed = progress.get("phaseElapsedSeconds")
    if isinstance(elapsed, (int, float)) and elapsed > 0:
        parts.append(f"phase={elapsed}s")
    return ", ".join(parts)


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
