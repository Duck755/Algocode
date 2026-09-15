"""Agent phase machine and tool loop."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from algocode.context.builder import ContextBuilder
from algocode.context.facts import FactLedger
from algocode.context.types import ToolExchange
from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import TaskId, TaskPhase, TaskStatus
from algocode.languages.types import BuildProfile
from algocode.ports import EventStore
from algocode.providers.errors import ContextOverflowError
from algocode.providers.types import (
    ModelRef,
    ModelRequest,
    ModelUsage,
    ToolCall,
)
from algocode.runtime.gates import PhaseGate
from algocode.runtime.task_lock import TaskRunLock
from algocode.security import SecretRedactor
from algocode.tools.types import ToolContext, ToolResult

PHASE_SEQUENCE: tuple[TaskPhase, ...] = (
    TaskPhase.CREATE,
    TaskPhase.ANALYZE,
    TaskPhase.BASELINE,
    TaskPhase.PLAN,
    TaskPhase.GENERATE_CANDIDATE,
    TaskPhase.IMPLEMENT,
    TaskPhase.VERIFY,
    TaskPhase.BENCHMARK,
    TaskPhase.COMPARE,
    TaskPhase.DECIDE,
    TaskPhase.REPORT,
)


@dataclass(frozen=True, slots=True)
class PhaseOutcome:
    status: str
    summary: str
    findings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    task_id: str
    status: str
    completed_phases: tuple[str, ...]
    turns: int
    tool_calls: int
    summary: str = ""
    outcomes: tuple[PhaseOutcome, ...] = field(default_factory=tuple)


class AgentRuntime:
    """Run the outer phase machine and inner tool loop."""

    def __init__(
        self,
        *,
        event_store: EventStore,
        task_service,
        provider,
        tool_registry,
        project_service,
        baseline_service,
        artifact_store,
        language_registry,
        correctness_service,
        benchmark_service,
        max_steps_per_phase: int = 20,
        max_tool_calls_per_phase: int = 50,
        build_profile: BuildProfile | None = None,
        candidate_service=None,
        resource_provider=None,
        redactor: SecretRedactor | None = None,
        context_window: int = 128_000,
        config_hash: str = "",
        policy_hash: str = "",
        database=None,
        protected_files: tuple[str, ...] = (),
        model: ModelRef | None = None,
    ) -> None:
        self._event_store = event_store
        self._task_service = task_service
        self._provider = provider
        self._tool_registry = tool_registry
        self._project_service = project_service
        self._baseline_service = baseline_service
        self._artifact_store = artifact_store
        self._language_registry = language_registry
        self._correctness_service = correctness_service
        self._benchmark_service = benchmark_service
        self._max_steps_per_phase = max_steps_per_phase
        self._max_tool_calls_per_phase = max_tool_calls_per_phase
        self._build_profile = build_profile or BuildProfile()
        self._candidate_service = candidate_service
        self._resource_provider = resource_provider
        self._redactor = redactor or SecretRedactor()
        self._database = database
        self._context_builder = ContextBuilder(
            context_window=context_window,
            config_hash=config_hash,
            policy_hash=policy_hash,
            tool_catalog_hash=_tool_catalog_hash(tool_registry),
        )
        self._phase_gate = PhaseGate()
        self._protected_files = protected_files
        self._model = model or ModelRef(provider_id="fake", model_id="deterministic")

    async def run(
        self,
        task_id: TaskId | str,
        *,
        candidate_workspace: str | Path | None = None,
        candidate_id: str | None = None,
        cancel_event: asyncio.Event | None = None,
        stop_after: TaskPhase = TaskPhase.REPORT,
    ) -> AgentRunResult:
        if self._database is None:
            return await self._run_unlocked(
                task_id,
                candidate_workspace=candidate_workspace,
                candidate_id=candidate_id,
                cancel_event=cancel_event,
                stop_after=stop_after,
            )
        async with TaskRunLock(self._database, str(task_id)):
            return await self._run_unlocked(
                task_id,
                candidate_workspace=candidate_workspace,
                candidate_id=candidate_id,
                cancel_event=cancel_event,
                stop_after=stop_after,
            )

    async def _run_unlocked(
        self,
        task_id: TaskId | str,
        *,
        candidate_workspace: str | Path | None = None,
        candidate_id: str | None = None,
        cancel_event: asyncio.Event | None = None,
        stop_after: TaskPhase = TaskPhase.REPORT,
    ) -> AgentRunResult:
        task = await self._task_service.get_task(task_id)
        project = await self._project_service.get(task.project_id)
        workspace = await self._workspace_for(
            project.root_path,
            task.id,
            candidate_workspace,
        )
        phases = _phases_from(task.current_phase, stop_after)
        completed: list[str] = []
        outcomes: list[PhaseOutcome] = []
        total_turns = 0
        total_tool_calls = 0
        correctness_result_id: str | None = None
        active_candidate_id = candidate_id
        active_workspace = workspace

        for phase in phases:
            candidates = []
            if self._candidate_service is not None:
                candidates = await self._candidate_service.list_for_task(task.id)
                if active_candidate_id is None and candidates:
                    active_candidate_id = str(candidates[0].id)
                    active_workspace = Path(candidates[0].workspace_ref)
            gate = self._phase_gate.evaluate(
                task=task,
                phase=phase,
                has_baseline=(await self._baseline_service.get_for_task(task.id) is not None),
                candidates=candidates,
                active_candidate_id=active_candidate_id,
                correctness_runs=await self._correctness_service.list_for_task(task.id),
                benchmark_runs=await self._benchmark_service.list_for_task(task.id),
            )
            if not gate.allowed:
                await self._append_gate_denied(str(task.id), phase, gate.reason)
                return AgentRunResult(
                    task_id=str(task.id),
                    status=TaskStatus.WAITING_USER.value,
                    completed_phases=tuple(completed),
                    turns=total_turns,
                    tool_calls=total_tool_calls,
                    summary=gate.reason,
                    outcomes=tuple(outcomes),
                )
            if cancel_event is not None and cancel_event.is_set():
                await self._append_cancelled(str(task.id), phase)
                await self._append_terminal(str(task.id), phase, TaskStatus.CANCELLED)
                return AgentRunResult(
                    task_id=str(task.id),
                    status=TaskStatus.CANCELLED.value,
                    completed_phases=tuple(completed),
                    turns=total_turns,
                    tool_calls=total_tool_calls,
                    summary="agent cancelled",
                    outcomes=tuple(outcomes),
                )
            await self._append_phase(str(task.id), phase, TaskStatus.RUNNING)
            outcome, phase_turns, phase_tool_calls, correctness_result_id = await self._run_phase(
                task_id=str(task.id),
                objective=task.objective,
                phase=phase,
                workspace=active_workspace,
                candidate_id=active_candidate_id,
                correctness_result_id=correctness_result_id,
                cancel_event=cancel_event,
            )
            outcomes.append(outcome)
            total_turns += phase_turns
            total_tool_calls += phase_tool_calls
            if outcome.status == "blocked":
                if outcome.summary == "cancelled":
                    await self._append_cancelled(str(task.id), phase)
                    await self._append_terminal(str(task.id), phase, TaskStatus.CANCELLED)
                    return AgentRunResult(
                        task_id=str(task.id),
                        status=TaskStatus.CANCELLED.value,
                        completed_phases=tuple(completed),
                        turns=total_turns,
                        tool_calls=total_tool_calls,
                        summary="agent cancelled",
                        outcomes=tuple(outcomes),
                    )
                await self._append_phase(str(task.id), phase, TaskStatus.WAITING_USER)
                return AgentRunResult(
                    task_id=str(task.id),
                    status=TaskStatus.WAITING_USER.value,
                    completed_phases=tuple(completed),
                    turns=total_turns,
                    tool_calls=total_tool_calls,
                    summary=outcome.summary,
                    outcomes=tuple(outcomes),
                )
            if outcome.status == "continue":
                await self._append_phase(str(task.id), phase, TaskStatus.FAILED)
                await self._append_terminal(str(task.id), phase, TaskStatus.FAILED)
                return AgentRunResult(
                    task_id=str(task.id),
                    status=TaskStatus.FAILED.value,
                    completed_phases=tuple(completed),
                    turns=total_turns,
                    tool_calls=total_tool_calls,
                    summary="tool loop ended without a phase result",
                    outcomes=tuple(outcomes),
                )
            completed.append(phase.value)

        await self._append_phase(str(task.id), phases[-1], TaskStatus.COMPLETED)
        await self._append_terminal(str(task.id), phases[-1], TaskStatus.COMPLETED)
        return AgentRunResult(
            task_id=str(task.id),
            status=TaskStatus.COMPLETED.value,
            completed_phases=tuple(completed),
            turns=total_turns,
            tool_calls=total_tool_calls,
            outcomes=tuple(outcomes),
        )

    async def _run_phase(
        self,
        *,
        task_id: str,
        objective: str,
        phase: TaskPhase,
        workspace: Path,
        candidate_id: str | None,
        correctness_result_id: str | None,
        cancel_event: asyncio.Event | None,
    ) -> tuple[PhaseOutcome, int, int, str | None]:
        tool_exchanges: list[ToolExchange] = []
        facts = FactLedger()
        facts.update(
            kind="task",
            key="task.objective",
            value=objective,
            source_fragment_id="objective",
        )
        tool_calls_used = 0
        turns_used = 0
        repeated: dict[str, int] = {}
        context_window_override: int | None = None
        force_compaction = False
        overflow_retries = 0
        for _ in range(self._max_steps_per_phase):
            if cancel_event is not None and cancel_event.is_set():
                return (
                    PhaseOutcome(status="blocked", summary="cancelled"),
                    turns_used,
                    tool_calls_used,
                    correctness_result_id,
                )
            task = await self._task_service.get_task(task_id)
            summaries = await self._context_summaries(task.id, candidate_id)
            await self._update_context_facts(facts, task.id, phase, candidate_id)
            snapshot = self._context_builder.build(
                task=task,
                phase=phase,
                model=self._model.model_id,
                **summaries,
                tool_exchanges=tuple(tool_exchanges),
                window_override=context_window_override,
                force_compaction=force_compaction,
                recent_tool_results=2 if force_compaction else 5,
                facts=facts.all(),
                tool_schema_text=json.dumps(
                    self._tool_registry.provider_schemas(),
                    ensure_ascii=True,
                    sort_keys=True,
                ),
            )
            await self._append_context(task_id, phase, snapshot)
            turns_used += 1
            await self._append_turn_started(task_id, phase, turns_used)
            request = ModelRequest(
                request_id=f"req_{uuid4().hex}",
                model=self._model,
                system="",
                messages=snapshot.to_messages(),
                tools=self._tool_registry.provider_schemas(),
                timeout_seconds=60,
                metadata={
                    "phase": phase.value,
                    "context_hash": snapshot.context_hash,
                },
            )
            try:
                response = await self._provider.complete(self._redactor.redact_value(request))
            except ContextOverflowError:
                if overflow_retries >= 2:
                    raise
                overflow_retries += 1
                current_window = context_window_override or self._context_builder.context_window
                context_window_override = max(2048, int(current_window * 0.7))
                force_compaction = True
                continue
            await self._append_turn_completed(task_id, phase, response.usage)
            if not response.tool_calls:
                return (
                    PhaseOutcome(
                        status="completed",
                        summary=response.text or "model completed without tool calls",
                    ),
                    turns_used,
                    tool_calls_used,
                    correctness_result_id,
                )
            for call in response.tool_calls:
                tool_calls_used += 1
                if tool_calls_used > self._max_tool_calls_per_phase:
                    return (
                        PhaseOutcome(
                            status="blocked",
                            summary="tool call budget exhausted",
                        ),
                        turns_used,
                        tool_calls_used - 1,
                        correctness_result_id,
                    )
                context = ToolContext(
                    task=task,
                    phase=phase,
                    workspace=workspace,
                    candidate_id=candidate_id,
                    correctness_result_id=correctness_result_id,
                    artifact_store=self._artifact_store,
                    language_registry=self._language_registry,
                    correctness_service=self._correctness_service,
                    benchmark_service=self._benchmark_service,
                    candidate_service=self._candidate_service,
                    resource_provider=self._resource_provider,
                    build_profile=self._build_profile,
                    protected_files=self._protected_files,
                )
                await self._append_tool_started(task_id, phase, call)
                result = await self._tool_registry.execute(call.name, call.arguments, context)
                await self._append_tool_completed(task_id, phase, call, result)
                tool_exchanges.append(ToolExchange(call=call, result=result))
                if call.name == "create_candidate" and result.status == "success":
                    created_id = result.structured.get("candidate_id")
                    created_workspace = result.structured.get("workspace_ref")
                    if isinstance(created_id, str):
                        candidate_id = created_id
                    if isinstance(created_workspace, str):
                        workspace = Path(created_workspace)
                if call.name == "run_correctness" and result.status == "success":
                    result_id = result.structured.get("result_id")
                    if isinstance(result_id, str):
                        correctness_result_id = result_id
                signature = json.dumps(
                    {
                        "name": call.name,
                        "arguments": call.arguments,
                        "result": result.status,
                        "summary": result.summary,
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                )
                repeated[signature] = repeated.get(signature, 0) + 1
                if repeated[signature] >= 3 and call.name != "submit_phase_result":
                    return (
                        PhaseOutcome(status="blocked", summary="no progress detected"),
                        turns_used,
                        tool_calls_used,
                        correctness_result_id,
                    )
                if call.name == "submit_phase_result":
                    return (
                        PhaseOutcome(
                            status=str(result.structured.get("status", "continue")),
                            summary=result.summary,
                            findings=tuple(result.structured.get("findings", [])),
                            blockers=tuple(result.structured.get("blockers", [])),
                        ),
                        turns_used,
                        tool_calls_used,
                        correctness_result_id,
                    )
        return (
            PhaseOutcome(status="blocked", summary="phase step budget exhausted"),
            turns_used,
            tool_calls_used,
            correctness_result_id,
        )

    async def _context_summaries(
        self,
        task_id: str,
        candidate_id: str | None,
    ) -> dict[str, str]:
        task = await self._task_service.get_task(task_id)
        project = await self._project_service.get(task.project_id)
        baseline = await self._baseline_service.get_for_task(task_id)
        candidate = None
        if candidate_id is not None and self._candidate_service is not None:
            candidate = await self._candidate_service.get(candidate_id)
        correctness_runs = await self._correctness_service.list_for_task(task_id)
        benchmark_runs = await self._benchmark_service.list_for_task(task_id)
        return {
            "project_summary": f"{project.name} ({project.language.value})",
            "config_summary": "Policy and tool catalog hashes are bound to this context.",
            "baseline_summary": (
                f"id={baseline.id}, revision={baseline.revision.value}, "
                f"snapshot={baseline.snapshot_hash}"
                if baseline is not None
                else "No baseline captured."
            ),
            "candidate_summary": (
                f"id={candidate.id}, status={candidate.status.value}, "
                f"patch_hash={candidate.patch_hash}"
                if candidate is not None
                else "No active candidate."
            ),
            "correctness_evidence": _evidence_summary(correctness_runs),
            "benchmark_evidence": _evidence_summary(benchmark_runs),
            "resources": "",
            "current_request": f"Continue {task.current_phase.value} using tool evidence.",
        }

    async def _update_context_facts(
        self,
        facts: FactLedger,
        task_id: str,
        phase: TaskPhase,
        candidate_id: str | None,
    ) -> None:
        facts.update(
            kind="phase",
            key="phase.current",
            value=phase.value,
            source_fragment_id="phase",
        )
        baseline = await self._baseline_service.get_for_task(task_id)
        if baseline is not None:
            facts.update(
                kind="baseline",
                key="baseline.revision",
                value=baseline.revision.value,
                source_fragment_id="baseline",
            )
        if candidate_id is not None and self._candidate_service is not None:
            candidate = await self._candidate_service.get(candidate_id)
            facts.update(
                kind="candidate",
                key="candidate.status",
                value=candidate.status.value,
                source_fragment_id="candidate",
            )

    async def _append_context(
        self,
        task_id: str,
        phase: TaskPhase,
        snapshot,
    ) -> None:
        payload = json.dumps(snapshot.payload(), ensure_ascii=False, sort_keys=True).encode()
        ref = await self._artifact_store.put(
            payload,
            kind="context-snapshot",
            mime_type="application/json",
            metadata={"task_id": task_id, "phase": phase.value},
        )
        seq = await self._next_seq(task_id)
        events = [
            _event(
                task_id,
                seq,
                EventType.CONTEXT_ASSEMBLED,
                {
                    "phase": phase.value,
                    "context_hash": snapshot.context_hash,
                    "estimated_tokens": snapshot.estimated_tokens,
                    "dropped_fragments": list(snapshot.dropped_fragments),
                    "snapshot_ref": _artifact_payload(ref),
                },
            )
        ]
        if snapshot.compacted:
            events.append(
                _event(
                    task_id,
                    seq + 1,
                    EventType.CONTEXT_COMPACTED,
                    {
                        "context_hash": snapshot.context_hash,
                        "dropped_fragments": list(snapshot.dropped_fragments),
                    },
                )
            )
        await self._event_store.append(task_id, seq - 1, tuple(events))

    async def _workspace_for(
        self,
        project_root: str,
        task_id,
        candidate_workspace: str | Path | None,
    ) -> Path:
        if candidate_workspace is not None:
            return Path(candidate_workspace)
        baseline = await self._baseline_service.get_for_task(task_id)
        if baseline is not None and baseline.workspace_ref is not None:
            return Path(baseline.workspace_ref)
        return Path(project_root)

    async def _append_terminal(
        self,
        task_id: str,
        phase: TaskPhase,
        status: TaskStatus,
    ) -> None:
        event_type = {
            TaskStatus.COMPLETED: EventType.TASK_COMPLETED,
            TaskStatus.FAILED: EventType.TASK_FAILED,
            TaskStatus.CANCELLED: EventType.TASK_CANCELLED,
        }[status]
        seq = await self._next_seq(task_id)
        timestamp = datetime.now(UTC).isoformat()
        await self._event_store.append(
            task_id,
            seq - 1,
            (
                _event(
                    task_id,
                    seq,
                    event_type,
                    {
                        "status": status.value,
                        "current_phase": phase.value,
                        "completed_at": (timestamp if status is TaskStatus.COMPLETED else None),
                    },
                ),
            ),
        )

    async def _append_phase(self, task_id: str, phase: TaskPhase, status: TaskStatus) -> None:
        seq = await self._next_seq(task_id)
        await self._event_store.append(
            task_id,
            seq - 1,
            (
                _event(
                    task_id,
                    seq,
                    EventType.TASK_PHASE_CHANGED,
                    {"current_phase": phase.value, "status": status.value},
                ),
            ),
        )

    async def _append_turn_started(self, task_id: str, phase: TaskPhase, turn: int) -> None:
        seq = await self._next_seq(task_id)
        await self._event_store.append(
            task_id,
            seq - 1,
            (
                _event(
                    task_id,
                    seq,
                    EventType.AGENT_TURN_STARTED,
                    {"phase": phase.value, "turn": turn},
                ),
            ),
        )

    async def _append_turn_completed(
        self,
        task_id: str,
        phase: TaskPhase,
        usage: ModelUsage,
    ) -> None:
        seq = await self._next_seq(task_id)
        await self._event_store.append(
            task_id,
            seq - 1,
            (
                _event(
                    task_id,
                    seq,
                    EventType.AGENT_TURN_COMPLETED,
                    {
                        "phase": phase.value,
                        "input_tokens": usage.input_tokens,
                        "output_tokens": usage.output_tokens,
                        "reasoning_tokens": usage.reasoning_tokens,
                    },
                ),
            ),
        )

    async def _append_tool_started(self, task_id: str, phase: TaskPhase, call: ToolCall) -> None:
        seq = await self._next_seq(task_id)
        await self._event_store.append(
            task_id,
            seq - 1,
            (
                _event(
                    task_id,
                    seq,
                    EventType.TOOL_CALL_STARTED,
                    {
                        "phase": phase.value,
                        "tool_call_id": call.id,
                        "name": call.name,
                        "arguments": call.arguments,
                    },
                ),
            ),
        )

    async def _append_tool_completed(
        self,
        task_id: str,
        phase: TaskPhase,
        call: ToolCall,
        result: ToolResult,
    ) -> None:
        seq = await self._next_seq(task_id)
        await self._event_store.append(
            task_id,
            seq - 1,
            (
                _event(
                    task_id,
                    seq,
                    EventType.TOOL_CALL_COMPLETED,
                    {
                        "phase": phase.value,
                        "tool_call_id": call.id,
                        "name": call.name,
                        "status": result.status,
                        "summary": result.summary,
                        "structured": result.structured,
                    },
                ),
            ),
        )

    async def _append_gate_denied(self, task_id: str, phase: TaskPhase, reason: str) -> None:
        seq = await self._next_seq(task_id)
        await self._event_store.append(
            task_id,
            seq - 1,
            (
                _event(
                    task_id,
                    seq,
                    EventType.PHASE_GATE_DENIED,
                    {"phase": phase.value, "reason": reason},
                ),
            ),
        )

    async def _append_cancelled(self, task_id: str, phase: TaskPhase) -> None:
        seq = await self._next_seq(task_id)
        await self._event_store.append(
            task_id,
            seq - 1,
            (
                _event(
                    task_id,
                    seq,
                    EventType.AGENT_CANCELLED,
                    {"phase": phase.value},
                ),
            ),
        )

    async def _next_seq(self, aggregate_id: str) -> int:
        events = await self._event_store.read(aggregate_id)
        return events[-1].seq + 1 if events else 1


def _tool_catalog_hash(registry) -> str:
    payload = [
        {"name": item.name, "schema": item.input_schema, "effects": item.effects}
        for item in registry.definitions()
    ]
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _evidence_summary(runs) -> str:
    if not runs:
        return "No evidence."
    return "\n".join(
        f"id={run.id}, target={run.target_kind}:{run.target_id}, status={run.status.value}"
        for run in runs[-5:]
    )


def _artifact_payload(ref) -> dict[str, str]:
    return {"uri": ref.uri, "sha256": ref.sha256}


def _phases_from(current: TaskPhase, stop_after: TaskPhase) -> tuple[TaskPhase, ...]:
    try:
        start = PHASE_SEQUENCE.index(current)
    except ValueError:
        start = 0
    end = PHASE_SEQUENCE.index(stop_after)
    return PHASE_SEQUENCE[start : end + 1]


def _event(
    aggregate_id: str,
    seq: int,
    event_type: EventType,
    payload: dict[str, object],
) -> EventEnvelope:
    return EventEnvelope(
        id=f"evt_{uuid4().hex}",
        aggregate_id=aggregate_id,
        seq=seq,
        type=event_type,
        payload=payload,
    )
