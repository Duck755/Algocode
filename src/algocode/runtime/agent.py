"""Agent phase machine and tool loop."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from algocode.context.builder import ContextBuilder
from algocode.context.facts import FactLedger
from algocode.context.types import ToolExchange
from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import (
    ArtifactRef,
    BenchmarkStatus,
    CandidateStatus,
    CorrectnessStatus,
    Language,
    TaskId,
    TaskPhase,
    TaskStatus,
)
from algocode.languages.types import BuildProfile
from algocode.ports import EventStore
from algocode.project_layout import ProjectLayout
from algocode.providers.errors import ContextOverflowError, ToolProtocolError
from algocode.providers.types import (
    ModelRef,
    ModelRequest,
    ModelUsage,
    ToolCall,
)
from algocode.profiling import collect_profile
from algocode.runtime.analysis import (
    AnalysisReport,
    ReadCoverage,
    analysis_summary_prompt,
    discover_required_files,
    parse_analysis_report,
)
from algocode.runtime.gates import PhaseGate
from algocode.runtime.model_log import (
    ModelCallLogger,
    model_call_duration_ms,
    model_error_traceback,
)
from algocode.runtime.optimization_record import OptimizationRecordStore
from algocode.runtime.planning import (
    OptimizationPlan,
)
from algocode.runtime.repair_memory import RepairMemoryStore
from algocode.runtime.task_lock import TaskRunLock
from algocode.security import SecretRedactor
from algocode.structured_output import StructuredOutputError, validate_model
from algocode.tools.types import ToolContext, ToolResult
from algocode.workspace import GitRepository

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
        max_steps_per_phase: int = 30,
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
        model_log_root: str | Path | None = None,
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
        self._analysis_report_text = ""
        self._optimization_plan_text = ""
        self._candidate_base_workspace: Path | None = None
        self._candidate_parent_candidate_id: str | None = None
        self._protected_files = protected_files
        self._model = model or ModelRef(provider_id="fake", model_id="deterministic")
        self._model_call_logger = (
            ModelCallLogger(model_log_root, redactor=self._redactor)
            if model_log_root is not None
            else None
        )
        self._optimization_record_root = (
            Path(model_log_root).expanduser().parent / "optimization-records"
            if model_log_root is not None
            else None
        )
        self._repair_memory = (
            RepairMemoryStore(
                Path(model_log_root).expanduser().parent / "repair-memory",
                redactor=self._redactor,
            )
            if model_log_root is not None
            else None
        )

    async def run(
        self,
        task_id: TaskId | str,
        *,
        candidate_workspace: str | Path | None = None,
        candidate_id: str | None = None,
        cancel_event: asyncio.Event | None = None,
        stop_after: TaskPhase = TaskPhase.REPORT,
        command_name: str = "optimize",
    ) -> AgentRunResult:
        if self._database is None:
            return await self._run_and_record(
                task_id,
                candidate_workspace=candidate_workspace,
                candidate_id=candidate_id,
                cancel_event=cancel_event,
                stop_after=stop_after,
                command_name=command_name,
            )
        async with TaskRunLock(self._database, str(task_id)):
            return await self._run_and_record(
                task_id,
                candidate_workspace=candidate_workspace,
                candidate_id=candidate_id,
                cancel_event=cancel_event,
                stop_after=stop_after,
                command_name=command_name,
            )

    async def _run_and_record(
        self,
        task_id: TaskId | str,
        *,
        candidate_workspace: str | Path | None = None,
        candidate_id: str | None = None,
        cancel_event: asyncio.Event | None = None,
        stop_after: TaskPhase = TaskPhase.REPORT,
        command_name: str = "optimize",
    ) -> AgentRunResult:
        started_at = datetime.now(UTC).isoformat()
        try:
            result = await self._run_unlocked(
                task_id,
                candidate_workspace=candidate_workspace,
                candidate_id=candidate_id,
                cancel_event=cancel_event,
                stop_after=stop_after,
            )
        except Exception as exc:
            await self._write_optimization_record(
                task_id=str(task_id),
                command=command_name,
                started_at=started_at,
                result=None,
                error=exc,
            )
            raise
        await self._write_optimization_record(
            task_id=str(task_id),
            command=command_name,
            started_at=started_at,
            result=result,
            error=None,
        )
        return result

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
        if not self._analysis_report_text:
            await self._restore_analysis_report(str(task.id))
        if not self._optimization_plan_text:
            await self._restore_optimization_plan(str(task.id))
        retry_boundary = await self._retry_candidate_ids(str(task.id))
        optimization_history = (
            await self._optimization_history(str(task.id)) if retry_boundary is not None else ""
        )
        optimization_records = (
            await self._optimization_records(str(task.id)) if retry_boundary is not None else ()
        )
        self._candidate_base_workspace = None
        self._candidate_parent_candidate_id = None
        project = await self._project_service.get(task.project_id)
        workspace = await self._workspace_for(
            project.root_path,
            task.id,
            candidate_workspace,
        )
        phases = list(_phases_from(task.current_phase, stop_after))
        completed: list[str] = []
        outcomes: list[PhaseOutcome] = []
        total_turns = 0
        total_tool_calls = 0
        correctness_result_id: str | None = None
        active_candidate_id = candidate_id
        active_workspace = workspace

        for index, phase in enumerate(phases):
            candidates = []
            correctness_runs = await self._correctness_service.list_for_task(task.id)
            benchmark_runs = await self._benchmark_service.list_for_task(task.id)
            if self._candidate_service is not None:
                candidates = await self._candidate_service.list_for_task(task.id)
                selectable = candidates
                retry_candidate_ids = await self._retry_candidate_ids(str(task.id))
                if retry_candidate_ids is not None:
                    selectable = [
                        candidate
                        for candidate in candidates
                        if str(candidate.id) in retry_candidate_ids
                    ]
                if active_candidate_id is None and selectable:
                    active_candidate_id = str(selectable[0].id)
                    active_workspace = Path(selectable[0].workspace_ref)
            if (
                phase is TaskPhase.VERIFY
                and self._candidate_service is not None
                and active_candidate_id is not None
            ):
                rejected_candidate = next(
                    (
                        candidate
                        for candidate in candidates
                        if str(candidate.id) == active_candidate_id
                        and candidate.status is CandidateStatus.REJECTED
                    ),
                    None,
                )
                if rejected_candidate is not None:
                    replacement = await self._candidate_service.create(task.id)
                    await self._append_phase(
                        str(task.id),
                        TaskPhase.GENERATE_CANDIDATE,
                        TaskStatus.RUNNING,
                    )
                    await self._append_phase(
                        str(task.id),
                        TaskPhase.GENERATE_CANDIDATE,
                        TaskStatus.COMPLETED,
                    )
                    active_candidate_id = str(replacement.id)
                    active_workspace = Path(replacement.workspace_ref)
                    candidates = [replacement, *candidates]
                    correctness_result_id = None
                    phases.insert(index + 1, TaskPhase.VERIFY)
                    phase = TaskPhase.IMPLEMENT
                    completed.append(TaskPhase.GENERATE_CANDIDATE.value)
                    outcomes.append(
                        PhaseOutcome(
                            status="completed",
                            summary=(
                                f"replaced rejected candidate {rejected_candidate.id} with "
                                f"{replacement.id}"
                            ),
                        )
                    )
            if active_candidate_id is not None and correctness_result_id is None:
                passed_correctness = next(
                    (
                        run
                        for run in correctness_runs
                        if run.target_kind == "candidate"
                        and run.target_id == active_candidate_id
                        and run.status is CorrectnessStatus.PASSED
                    ),
                    None,
                )
                if passed_correctness is not None:
                    correctness_result_id = passed_correctness.id
            gate = self._phase_gate.evaluate(
                task=task,
                phase=phase,
                has_baseline=(await self._baseline_service.get_for_task(task.id) is not None),
                candidates=candidates,
                active_candidate_id=active_candidate_id,
                correctness_runs=correctness_runs,
                benchmark_runs=benchmark_runs,
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
            auto_outcome = await self._try_auto_phase(
                task=task,
                phase=phase,
                candidate_id=active_candidate_id,
                correctness_runs=correctness_runs,
                benchmark_runs=benchmark_runs,
                workspace=active_workspace,
            )
            if auto_outcome is not None:
                outcomes.append(auto_outcome)
                completed.append(phase.value)
                continue
            outcome, phase_turns, phase_tool_calls, correctness_result_id = await self._run_phase(
                task_id=str(task.id),
                objective=task.objective,
                phase=phase,
                workspace=active_workspace,
                candidate_id=active_candidate_id,
                correctness_result_id=correctness_result_id,
                cancel_event=cancel_event,
                optimization_history=optimization_history,
                retry_records=optimization_records,
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

    async def _try_auto_phase(
        self,
        *,
        task,
        phase: TaskPhase,
        candidate_id: str | None,
        correctness_runs,
        benchmark_runs,
        workspace: Path,
    ) -> PhaseOutcome | None:
        if phase is TaskPhase.BASELINE:
            baseline = await self._baseline_service.get_for_task(task.id)
            if baseline is not None:
                return PhaseOutcome(
                    status="completed",
                    summary=f"baseline {baseline.id} already exists",
                )
        if phase is TaskPhase.PLAN and self._optimization_plan_text:
            return PhaseOutcome(
                status="completed",
                summary="optimization plan already exists",
            )
        if phase is TaskPhase.GENERATE_CANDIDATE and candidate_id is not None:
            return PhaseOutcome(
                status="completed",
                summary=f"candidate {candidate_id} already exists",
            )
        if (
            phase is TaskPhase.VERIFY
            and candidate_id is not None
            and any(
                run.target_kind == "candidate"
                and run.target_id == candidate_id
                and run.status is CorrectnessStatus.PASSED
                for run in correctness_runs
            )
        ):
            layout = ProjectLayout.from_root(workspace)
            if layout.contract_test() is None:
                return PhaseOutcome(
                    status="completed",
                    summary=f"candidate {candidate_id} correctness already passed",
                )
        benchmark = next(
            (
                run
                for run in benchmark_runs
                if run.target_kind == "candidate"
                and run.target_id == candidate_id
                and run.status is BenchmarkStatus.COMPLETED
                and run.comparison_ref is not None
            ),
            None,
        )
        if phase is TaskPhase.BENCHMARK and benchmark is not None:
            return PhaseOutcome(
                status="completed",
                summary=f"benchmark {benchmark.id} already exists",
            )
        if phase not in {TaskPhase.COMPARE, TaskPhase.DECIDE, TaskPhase.REPORT}:
            return None
        if candidate_id is None:
            return None
        if benchmark is None:
            return None
        comparison = await self._benchmark_service.read_comparison(benchmark)
        if not comparison:
            return None
        improvement = float(comparison.get("improvement_percent", 0.0))
        valid = comparison.get("valid") is True
        summary = f"benchmark {benchmark.id}: valid={valid}, improvement={improvement:.6f}%"
        return PhaseOutcome(status="completed", summary=summary)

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
        optimization_history: str = "",
        retry_records: tuple[dict[str, object], ...] = (),
    ) -> tuple[PhaseOutcome, int, int, str | None]:
        tool_exchanges: list[ToolExchange] = []
        facts = FactLedger()
        coverage = (
            ReadCoverage(discover_required_files(workspace)) if phase is TaskPhase.ANALYZE else None
        )
        facts.update(
            kind="task",
            key="task.objective",
            value=objective,
            source_fragment_id="objective",
        )
        tool_calls_used = 0
        turns_used = 0
        repeated: dict[str, int] = {}
        no_progress_warnings = 0
        validation_failures = 0
        protocol_parse_failures = 0
        applied_patch_snapshot_hash: str | None = None
        candidate_check_snapshot_hash: str | None = None
        repair_context = ""
        active_optimization_history = optimization_history
        repair_patch_required = False
        contract_passed = False
        layout = ProjectLayout.from_root(workspace)
        contract_required = layout.contract_test() is not None
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
            if coverage is not None:
                summaries["current_request"] = (
                    f"{coverage.summary()} Read each required file completely in at least "
                    "two different turns. You may call read_required_files to cover all files "
                    "in one turn. Do not call submission tools; Runtime will end this phase "
                    "automatically when coverage is complete."
                )
            elif phase is TaskPhase.VERIFY and layout.correctness_spec().is_file():
                if contract_required:
                    correctness_spec_path = layout.correctness_spec_relative()
                    summaries["current_request"] = (
                        f'Call run_correctness with spec_path="{correctness_spec_path}", '
                        "then call run_contract. Do not reconstruct either specification."
                    )
                else:
                    correctness_spec_path = layout.correctness_spec_relative()
                    summaries["current_request"] = (
                        f'Call run_correctness with spec_path="{correctness_spec_path}". '
                        "Do not reconstruct or replace the correctness specification."
                    )
            elif phase is TaskPhase.BENCHMARK and layout.benchmark_spec().is_file():
                summaries["current_request"] = (
                    f'Call run_benchmark with spec_path="{layout.benchmark_spec_relative()}". '
                    "Do not reconstruct or replace the benchmark specification."
                )
            elif phase is TaskPhase.IMPLEMENT and applied_patch_snapshot_hash is not None:
                summaries["current_request"] = (
                    "A candidate mutation has been applied. Call run_candidate_check now. If it "
                    'passes, call submit_phase_result with phase="implement", '
                    'status="completed", and result={"changedFiles":[...]}. If it fails, fix '
                    "the candidate and run the check again."
                )
            if repair_context:
                summaries["current_request"] = (
                    "A candidate check failed. Use the repair-context fragment, patch the "
                    "candidate now, then run run_candidate_check again."
                )
            if phase is TaskPhase.PLAN:
                summaries["current_request"] = (
                    "Analysis is complete. Do not inspect files or task state. Submit one "
                    "OptimizationPlan now with submit_optimization_plan. Use the AnalysisReport "
                    "as the source of truth, including AnalysisReport.profile hotspots. "
                    "Justify each step against a hotspot or verified evidence; report missing "
                    "evidence as a risk or blocker instead of attempting more reads."
                )
                if active_optimization_history:
                    summaries["current_request"] += (
                        " This is a retry. Base the decision on the LAST ATTEMPT, not the "
                        "global best. Set retryDecision.mode to continue, pivot, or rollback. "
                        "Continue only when the last direction is not exhausted; otherwise pivot. "
                        "Rollback first when the last attempt regressed relative to its parent."
                    )
            phase_tools = self._tool_schemas_for_phase(phase)
            phase_tool_names = {
                str(schema.get("name")) for schema in phase_tools if schema.get("name")
            }
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
                repair_context=repair_context,
                optimization_history=active_optimization_history,
                tool_schema_text=json.dumps(
                    phase_tools,
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
                tools=phase_tools,
                timeout_seconds=60,
                metadata={
                    "phase": phase.value,
                    "context_hash": snapshot.context_hash,
                },
            )
            try:
                response = await self._complete_model(
                    request,
                    task_id=str(task.id),
                    phase=phase,
                    turn=turns_used,
                )
            except ToolProtocolError as exc:
                protocol_parse_failures += 1
                call = ToolCall(
                    id=exc.call_id or f"invalid_tool_arguments_{turns_used}",
                    name="invalid_tool_arguments",
                    arguments={
                        "tool": exc.tool_name or "unknown",
                        "parse_error": exc.parse_error,
                        "raw_arguments": exc.raw_arguments[:2000],
                    },
                )
                result = ToolResult(
                    status="error",
                    summary=(
                        f"Invalid JSON arguments for {exc.tool_name or 'the tool call'}. "
                        "Reissue the same logical tool call with valid JSON matching its schema. "
                        f"Parse error: {exc.parse_error}"
                    ),
                    structured={
                        "invalid_tool_arguments": True,
                        "tool": exc.tool_name or "unknown",
                        "parse_error": exc.parse_error,
                    },
                )
                await self._append_tool_started(task_id, phase, call)
                await self._append_tool_completed(task_id, phase, call, result)
                tool_exchanges.append(ToolExchange(call=call, result=result))
                if protocol_parse_failures >= 3:
                    return (
                        PhaseOutcome(
                            status="blocked",
                            summary="model repeatedly emitted invalid JSON tool arguments",
                        ),
                        turns_used,
                        tool_calls_used,
                        correctness_result_id,
                    )
                continue
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
                if coverage is not None and not coverage.complete:
                    tool_exchanges.append(
                        ToolExchange(
                            call=ToolCall(
                                id=f"coverage_{turns_used}",
                                name="analysis_coverage",
                                arguments={},
                            ),
                            result=ToolResult(
                                status="error",
                                summary=coverage.summary(),
                                structured=coverage.payload(),
                            ),
                        )
                    )
                    continue
                if phase in {TaskPhase.PLAN, TaskPhase.IMPLEMENT}:
                    required_tool = (
                        "submit_optimization_plan"
                        if phase is TaskPhase.PLAN
                        else "submit_phase_result"
                    )
                    tool_exchanges.append(
                        ToolExchange(
                            call=ToolCall(
                                id=f"submit_required_{turns_used}",
                                name=required_tool,
                                arguments={},
                            ),
                            result=ToolResult(
                                status="error",
                                summary=(
                                    f"{phase.value} requires {required_tool} with "
                                    "validated structured evidence"
                                ),
                                structured={"phase": phase.value, "submit_required": True},
                            ),
                        )
                    )
                    continue
                incomplete_reason = self._incomplete_runtime_phase_reason(
                    phase=phase,
                    correctness_result_id=correctness_result_id,
                    contract_required=contract_required,
                    contract_passed=contract_passed,
                )
                if incomplete_reason is not None:
                    return (
                        PhaseOutcome(status="blocked", summary=incomplete_reason),
                        turns_used,
                        tool_calls_used,
                        correctness_result_id,
                    )
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
                submission_failed = False
                validated_plan: OptimizationPlan | None = None
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
                    candidate_base_workspace=self._candidate_base_workspace,
                    candidate_parent_candidate_id=(self._candidate_parent_candidate_id),
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
                if repair_patch_required and call.name not in {
                    "apply_patch",
                    "write_file",
                    "edit_file",
                }:
                    result = ToolResult(
                        status="error",
                        summary=(
                            "candidate repair requires a code change before another tool call; "
                            "use apply_patch, write_file, or edit_file"
                        ),
                        structured={"repair_patch_required": True},
                    )
                elif call.name in phase_tool_names:
                    result = await self._tool_registry.execute(call.name, call.arguments, context)
                else:
                    result = ToolResult(
                        status="error",
                        summary=(f"tool {call.name} is not available in phase {phase.value}"),
                        structured={
                            "disallowed_tool": call.name,
                            "phase": phase.value,
                        },
                    )
                if call.name == "create_candidate" and result.status == "success":
                    created_id = result.structured.get("candidate_id")
                    created_workspace = result.structured.get("workspace_ref")
                    if isinstance(created_id, str):
                        candidate_id = created_id
                    if isinstance(created_workspace, str):
                        workspace = Path(created_workspace)
                if (
                    coverage is not None
                    and call.name in {"read_file", "read_required_files"}
                    and result.status == "success"
                    and not result.truncated
                ):
                    if call.name == "read_file":
                        path = call.arguments.get("path")
                        if isinstance(path, str):
                            coverage.record_read(path, turns_used)
                    else:
                        files = result.structured.get("files")
                        if isinstance(files, list):
                            for item in files:
                                if isinstance(item, dict) and isinstance(item.get("path"), str):
                                    coverage.record_read(str(item["path"]), turns_used)
                if call.name == "run_correctness" and result.status == "success":
                    result_id = result.structured.get("result_id")
                    if isinstance(result_id, str):
                        correctness_result_id = result_id
                if call.name == "run_candidate_check" and result.status == "success":
                    snapshot_hash = result.structured.get("snapshot_hash")
                    if isinstance(snapshot_hash, str):
                        candidate_check_snapshot_hash = snapshot_hash
                    repair_context = ""
                    repair_patch_required = False
                if call.name == "run_candidate_check" and result.status == "error":
                    repair_context = await self._record_candidate_check_failure(
                        task_id=task_id,
                        candidate_id=candidate_id,
                        workspace=workspace,
                        result=result,
                    )
                    if repair_context:
                        repair_patch_required = True
                if call.name == "run_contract" and result.status == "success":
                    contract_passed = True
                if (
                    call.name in {"apply_patch", "write_file", "edit_file"}
                    and result.status == "success"
                ):
                    candidate_check_snapshot_hash = None
                    repair_patch_required = False
                    repair_context = ""
                    snapshot_hash = result.structured.get("snapshot_hash")
                    if isinstance(snapshot_hash, str):
                        applied_patch_snapshot_hash = snapshot_hash
                if (
                    phase is TaskPhase.VERIFY
                    and call.name == "run_correctness"
                    and result.status == "error"
                    and isinstance(result.structured.get("result_id"), str)
                ):
                    return (
                        PhaseOutcome(
                            status="blocked",
                            summary=(
                                "candidate correctness failed; repair the candidate before retrying"
                            ),
                        ),
                        turns_used,
                        tool_calls_used,
                        correctness_result_id,
                    )
                if (
                    phase is TaskPhase.VERIFY
                    and call.name == "run_contract"
                    and result.status == "error"
                    and "exit_code" in result.structured
                ):
                    return (
                        PhaseOutcome(
                            status="blocked",
                            summary=(
                                "candidate contract failed; repair the candidate before retrying"
                            ),
                        ),
                        turns_used,
                        tool_calls_used,
                        correctness_result_id,
                    )
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
                no_progress = repeated[signature] >= 3 and call.name not in {
                    "submit_phase_result",
                    "submit_optimization_plan",
                }
                if no_progress:
                    repeated[signature] = 0
                    no_progress_warnings += 1
                    result = ToolResult(
                        status="error",
                        summary=(
                            f"STOP REPEATING {call.name}: the same tool call repeated three times. "
                            "Use a different tool or different arguments. Runtime completes "
                            "phases automatically when their required evidence exists."
                        ),
                        structured={
                            "no_progress": True,
                            "tool": call.name,
                        },
                    )
                if (
                    call.name == "submit_phase_result"
                    and result.status == "success"
                    and result.structured.get("status") == "completed"
                ):
                    try:
                        validation, validated_plan = await self._validate_phase_submission(
                            task_id=task_id,
                            phase=phase,
                            arguments=call.arguments,
                            candidate_id=candidate_id,
                            applied_patch_snapshot_hash=applied_patch_snapshot_hash,
                            candidate_check_snapshot_hash=candidate_check_snapshot_hash,
                        )
                    except ValueError as exc:
                        submission_failed = True
                        result = ToolResult(
                            status="error",
                            summary=f"phase result validation failed: {exc}",
                            structured={
                                "validation_failed": True,
                                "phase": phase.value,
                            },
                        )
                    else:
                        result = ToolResult(
                            status="success",
                            summary=result.summary,
                            structured={**result.structured, "validation": validation},
                        )
                await self._append_tool_completed(task_id, phase, call, result)
                tool_exchanges.append(
                    ToolExchange(
                        call=call,
                        result=result,
                        reasoning_content=response.reasoning,
                    )
                )
                if submission_failed:
                    validation_failures += 1
                    if validation_failures >= 3:
                        return (
                            PhaseOutcome(
                                status="blocked",
                                summary=(
                                    f"phase result validation failed repeatedly: {result.summary}"
                                ),
                            ),
                            turns_used,
                            tool_calls_used,
                            correctness_result_id,
                        )
                    continue
                auto_completed = (
                    (
                        phase is TaskPhase.GENERATE_CANDIDATE
                        and call.name == "create_candidate"
                        and result.status == "success"
                    )
                    or (
                        phase is TaskPhase.VERIFY
                        and call.name == "run_correctness"
                        and result.status == "success"
                        and correctness_result_id is not None
                        and (not contract_required or contract_passed)
                    )
                    or (
                        phase is TaskPhase.VERIFY
                        and call.name == "run_contract"
                        and result.status == "success"
                        and correctness_result_id is not None
                    )
                    or (
                        phase is TaskPhase.BENCHMARK
                        and call.name == "run_benchmark"
                        and result.status == "success"
                    )
                )
                if auto_completed:
                    return (
                        PhaseOutcome(
                            status="completed",
                            summary=f"{call.name} completed phase {phase.value}",
                        ),
                        turns_used,
                        tool_calls_used,
                        correctness_result_id,
                    )
                if coverage is not None and coverage.complete:
                    return await self._complete_analysis(
                        task_id=task_id,
                        objective=objective,
                        workspace=workspace,
                        phase=phase,
                        tool_exchanges=tool_exchanges,
                        facts=facts,
                        coverage=coverage,
                        turns_used=turns_used,
                        tool_calls_used=tool_calls_used,
                        correctness_result_id=correctness_result_id,
                    )
                if no_progress and no_progress_warnings >= 3:
                    return (
                        PhaseOutcome(status="blocked", summary="no progress detected"),
                        turns_used,
                        tool_calls_used,
                        correctness_result_id,
                    )
                if (
                    phase is TaskPhase.PLAN
                    and call.name == "submit_optimization_plan"
                    and result.status == "success"
                ):
                    try:
                        plan = validate_model(
                            result.structured.get("optimization_plan") or {},
                            OptimizationPlan,
                            label="optimization plan tool result",
                        )
                        if retry_records:
                            await self._resolve_retry_base(
                                plan=plan,
                                retry_records=retry_records,
                            )
                    except StructuredOutputError as exc:
                        validation_failures += 1
                        result = ToolResult(
                            status="error",
                            summary=str(exc),
                            structured={"validation_errors": str(exc), "tool": call.name},
                        )
                        if validation_failures >= 3:
                            return (
                                PhaseOutcome(
                                    status="blocked",
                                    summary="optimization plan validation failed repeatedly",
                                ),
                                turns_used,
                                tool_calls_used,
                                correctness_result_id,
                            )
                    else:
                        await self._persist_optimization_plan(task_id=task_id, plan=plan)
                        return (
                            PhaseOutcome(
                                status="completed",
                                summary=plan.summary,
                            ),
                            turns_used,
                            tool_calls_used,
                            correctness_result_id,
                        )
                if call.name == "submit_phase_result":
                    if validated_plan is not None:
                        await self._persist_optimization_plan(
                            task_id=task_id,
                            plan=validated_plan,
                        )
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

    async def _record_candidate_check_failure(
        self,
        *,
        task_id: str,
        candidate_id: str | None,
        workspace: Path,
        result: ToolResult,
    ) -> str:
        if self._repair_memory is None or candidate_id is None:
            return ""

        repository = await GitRepository.discover(workspace)
        snapshot = await repository.capture_snapshot(workspace)
        changed_files = await repository.changed_files(workspace)

        memory = await self._repair_memory.record(
            scope_id=task_id,
            phase=TaskPhase.IMPLEMENT.value,
            candidate_id=candidate_id,
            tool_name="run_candidate_check",
            failure={
                "summary": result.summary,
                "structured": result.structured,
            },
            snapshot_hash=snapshot.snapshot_hash,
            changed_files=changed_files,
            diff=snapshot.patch.decode(errors="replace"),
        )
        return self._repair_memory.render_brief(memory=memory)

    @staticmethod
    def _incomplete_runtime_phase_reason(
        *,
        phase: TaskPhase,
        correctness_result_id: str | None,
        contract_required: bool,
        contract_passed: bool,
    ) -> str | None:
        if phase is TaskPhase.VERIFY:
            if correctness_result_id is None:
                return "candidate correctness must pass before verify can complete"
            if contract_required and not contract_passed:
                return "contract tests must pass before verify can complete"
        if phase is TaskPhase.BENCHMARK:
            return "valid benchmark evidence is required before benchmark can complete"
        if phase in {TaskPhase.COMPARE, TaskPhase.DECIDE, TaskPhase.REPORT}:
            return f"{phase.value} requires submit_phase_result before completion"
        return None

    async def _complete_model(
        self,
        request: ModelRequest,
        *,
        task_id: str,
        phase: TaskPhase,
        turn: int,
    ) -> Any:
        started = time.perf_counter()
        redacted = self._redactor.redact_value(request)
        try:
            response = await self._provider.complete(redacted)
        except Exception as exc:
            if self._model_call_logger is not None:
                await self._model_call_logger.record(
                    scope_id=task_id,
                    task_id=task_id,
                    phase=phase.value,
                    turn=turn,
                    request=redacted,
                    duration_ms=model_call_duration_ms(started),
                    error=exc,
                    traceback_text=model_error_traceback(),
                )
            raise
        if self._model_call_logger is not None:
            await self._model_call_logger.record(
                scope_id=task_id,
                task_id=task_id,
                phase=phase.value,
                turn=turn,
                request=redacted,
                response=response,
                duration_ms=model_call_duration_ms(started),
            )
        return response

    async def _validate_phase_submission(
        self,
        *,
        task_id: str,
        phase: TaskPhase,
        arguments: dict[str, object],
        candidate_id: str | None,
        applied_patch_snapshot_hash: str | None,
        candidate_check_snapshot_hash: str | None,
    ) -> tuple[dict[str, object], OptimizationPlan | None]:
        if phase not in {TaskPhase.PLAN, TaskPhase.IMPLEMENT}:
            return ({"phase": phase.value, "valid": True}, None)
        raw_result = arguments.get("result")
        if not isinstance(raw_result, dict):
            raise ValueError("submit_phase_result.result must be an object")

        if phase is TaskPhase.PLAN:
            raw_plan = raw_result.get("optimizationPlan")
            if not isinstance(raw_plan, dict):
                raw_plan = raw_result.get("plan")
            if not isinstance(raw_plan, dict):
                raw_plan = raw_result
            try:
                plan = OptimizationPlan.model_validate(raw_plan)
            except ValueError as exc:
                raise ValueError(f"invalid OptimizationPlan: {exc}") from exc
            return (
                {
                    "phase": phase.value,
                    "valid": True,
                    "step_count": len(plan.steps),
                },
                plan,
            )

        if phase is TaskPhase.IMPLEMENT:
            if candidate_id is None or self._candidate_service is None:
                raise ValueError("implement phase requires an active candidate")
            candidate = await self._candidate_service.get(candidate_id)
            if str(candidate.task_id) != str(task_id):
                raise ValueError("candidate does not belong to the current task")
            if candidate.status not in {
                CandidateStatus.GENERATED,
                CandidateStatus.EDITING,
            }:
                raise ValueError(f"candidate status {candidate.status.value} cannot be submitted")
            if applied_patch_snapshot_hash is None:
                raise ValueError("apply_patch must succeed before implement can complete")

            workspace = Path(candidate.workspace_ref)
            candidate_check_required = (
                ProjectLayout.from_root(workspace).correctness_spec().is_file()
            )
            if candidate_check_required and candidate_check_snapshot_hash is None:
                raise ValueError("run_candidate_check must pass before implement can complete")
            repository = await GitRepository.discover(workspace)
            snapshot = await repository.capture_snapshot(workspace)
            if candidate_check_required:
                if snapshot.snapshot_hash != candidate_check_snapshot_hash:
                    raise ValueError(
                        "candidate workspace changed after the last successful check; "
                        "run run_candidate_check again"
                    )
            elif snapshot.snapshot_hash != applied_patch_snapshot_hash:
                raise ValueError("candidate workspace changed after the successful patch")
            changed_files = await repository.changed_files(workspace)
            if not changed_files:
                raise ValueError("candidate workspace has no changed files")

            protected_changed = tuple(
                path
                for path in changed_files
                if any(
                    path == pattern.rstrip("/") or path.startswith(f"{pattern.rstrip('/')}/")
                    for pattern in self._protected_files
                )
            )
            if protected_changed:
                raise ValueError(
                    f"candidate modifies protected files: {', '.join(protected_changed)}"
                )

            claimed_candidate = raw_result.get("candidateId") or raw_result.get("candidate_id")
            if claimed_candidate is not None and str(claimed_candidate) != candidate_id:
                raise ValueError("submitted candidateId does not match the active candidate")
            claimed_hash = raw_result.get("patchHash") or raw_result.get("snapshotHash")
            if claimed_hash is not None and str(claimed_hash) != snapshot.snapshot_hash:
                raise ValueError("submitted patch hash does not match the candidate workspace")
            claimed_files = raw_result.get("changedFiles")
            if claimed_files is not None:
                if not isinstance(claimed_files, list) or not {
                    str(path) for path in claimed_files
                }.issubset(set(changed_files)):
                    raise ValueError(
                        "submitted changedFiles does not match the candidate workspace: "
                        f"actual {sorted(changed_files)}, received {claimed_files}"
                    )

            return (
                {
                    "phase": phase.value,
                    "valid": True,
                    "candidate_id": candidate_id,
                    "patch_hash": snapshot.snapshot_hash,
                    "changed_files": list(changed_files),
                },
                None,
            )

        return ({"phase": phase.value, "valid": True}, None)

    async def _persist_optimization_plan(
        self,
        *,
        task_id: str,
        plan: OptimizationPlan,
    ) -> None:
        plan_payload = json.dumps(
            plan.model_dump(by_alias=True, mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        self._optimization_plan_text = plan_payload
        ref = await self._artifact_store.put(
            plan_payload.encode("utf-8"),
            kind="optimization-plan",
            mime_type="application/json",
            metadata={"task_id": task_id, "phase": TaskPhase.PLAN.value},
        )
        await self._append_plan_completed(
            task_id=task_id,
            plan=plan,
            ref=ref,
        )

    async def _complete_analysis(
        self,
        *,
        task_id: str,
        objective: str,
        workspace: Path,
        phase: TaskPhase,
        tool_exchanges: list[ToolExchange],
        facts: FactLedger,
        coverage: ReadCoverage,
        turns_used: int,
        tool_calls_used: int,
        correctness_result_id: str | None,
    ) -> tuple[PhaseOutcome, int, int, str | None]:
        previous_error: str | None = None
        facts.update(
            kind="analysis",
            key="analysis.coverage",
            value=coverage.summary(),
            source_fragment_id="analysis",
        )
        for _ in range(3):
            task = await self._task_service.get_task(task_id)
            summaries = await self._context_summaries(task.id, None)
            summaries["current_request"] = analysis_summary_prompt(
                coverage,
                previous_error=previous_error,
            )
            snapshot = self._context_builder.build(
                task=task,
                phase=phase,
                model=self._model.model_id,
                **summaries,
                tool_exchanges=tuple(tool_exchanges),
                recent_tool_results=max(10, len(tool_exchanges)),
                facts=facts.all(),
                tool_schema_text="",
            )
            await self._append_context(task_id, phase, snapshot)
            turns_used += 1
            await self._append_turn_started(task_id, phase, turns_used)
            request = ModelRequest(
                request_id=f"req_{uuid4().hex}",
                model=self._model,
                system="",
                messages=snapshot.to_messages(),
                tools=(),
                response_format={"type": "json_object"},
                timeout_seconds=60,
                metadata={"phase": phase.value, "stage": "analysis_summary"},
            )
            response = await self._complete_model(
                request,
                task_id=task_id,
                phase=phase,
                turn=turns_used,
            )
            await self._append_turn_completed(task_id, phase, response.usage)
            if response.tool_calls:
                previous_error = "analysis summary must not call tools"
                continue
            try:
                report = parse_analysis_report(response.text)
            except ValueError as exc:
                previous_error = str(exc)
                continue
            if self._protected_files:
                report = report.model_copy(update={"protected_files": tuple(self._protected_files)})
            profile_payload = await self._collect_profile_payload(workspace, report)
            report = report.model_copy(update={"profile": profile_payload})
            report_payload = json.dumps(
                report.model_dump(by_alias=True, mode="json"),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            self._analysis_report_text = report_payload
            ref = await self._artifact_store.put(
                report_payload.encode("utf-8"),
                kind="analysis-report",
                mime_type="application/json",
                metadata={"task_id": task_id, "phase": phase.value},
            )
            findings = tuple(
                [f"{item.path}: {item.role}" for item in report.files]
                + [item.description for item in report.optimization_candidates]
            )
            await self._append_analysis_completed(
                task_id=task_id,
                phase=phase,
                report=report,
                coverage=coverage,
                ref=ref,
            )
            return (
                PhaseOutcome(
                    status="completed",
                    summary=coverage.summary(),
                    findings=findings,
                ),
                turns_used,
                tool_calls_used,
                correctness_result_id,
            )
        return (
            PhaseOutcome(
                status="blocked",
                summary=f"analysis summary failed validation: {previous_error}",
            ),
            turns_used,
            tool_calls_used,
            correctness_result_id,
        )

    async def _collect_profile_payload(
        self,
        workspace: Path,
        report: AnalysisReport,
    ) -> dict[str, object]:
        try:
            detected = await self._language_registry.detect(workspace)
            language = detected.primary_language or Language.PYTHON
            commands = report.entrypoint_commands or await self._infer_profile_commands(
                workspace,
                language,
            )
            profile = await collect_profile(
                workspace=workspace,
                language=language,
                commands=commands,
                sandbox_runner=self._language_registry.sandbox_runner,
                timeout_seconds=self._build_profile.timeout_seconds,
            )
        except Exception as exc:
            return {
                "available": False,
                "tool": "profiler",
                "error": str(exc),
                "text": f"Profiler unavailable: {exc}",
            }
        payload = profile.payload()
        payload["text"] = self._redactor.redact_text(str(payload.get("text", "")))
        return payload

    async def _infer_profile_commands(
        self,
        workspace: Path,
        language: Language,
    ) -> tuple[tuple[str, ...], ...]:
        if language is Language.PYTHON:
            main_path = workspace / "main.py"
            if main_path.exists():
                return ((sys.executable, str(main_path)),)
            sources = sorted(
                path
                for path in workspace.rglob("*.py")
                if path.is_file() and ".algocode" not in path.parts
            )
            return ((sys.executable, str(sources[0])),) if sources else ()
        if language is Language.CPP:
            adapter = self._language_registry.adapter_for(Language.CPP)
            build_result = await adapter.build(workspace, self._build_profile)
            return (build_result.run_command,) if build_result.run_command else ()
        return ()

    async def _restore_analysis_report(self, task_id: str) -> None:
        events = await self._event_store.read(task_id)
        for event in reversed(events):
            if event.type is not EventType.ANALYSIS_COMPLETED:
                continue
            payload = event.payload.get("analysis_ref")
            if not isinstance(payload, dict):
                return
            ref = ArtifactRef(uri=str(payload["uri"]), sha256=str(payload["sha256"]))
            content = await self._artifact_store.read_bytes(ref)
            self._analysis_report_text = content.decode("utf-8")
            return

    async def _restore_optimization_plan(self, task_id: str) -> None:
        events = await self._event_store.read(task_id)
        for event in reversed(events):
            if event.type is EventType.TASK_RETRY_REQUESTED:
                return
            if event.type is not EventType.PLAN_COMPLETED:
                continue
            payload = event.payload.get("plan_ref")
            if not isinstance(payload, dict):
                return
            ref = ArtifactRef(uri=str(payload["uri"]), sha256=str(payload["sha256"]))
            content = await self._artifact_store.read_bytes(ref)
            self._optimization_plan_text = content.decode("utf-8")
            return

    async def _retry_candidate_ids(self, task_id: str) -> set[str] | None:
        events = await self._event_store.read(task_id)
        cutoff = next(
            (
                event.seq
                for event in reversed(events)
                if event.type is EventType.TASK_RETRY_REQUESTED
            ),
            None,
        )
        if cutoff is None:
            return None
        return {
            str(event.payload.get("candidate_id"))
            for event in events
            if event.seq > cutoff
            and event.type is EventType.CANDIDATE_CREATED
            and event.payload.get("candidate_id")
        }

    async def _optimization_history(self, task_id: str) -> str:
        if self._optimization_record_root is None:
            return ""
        store = OptimizationRecordStore(self._optimization_record_root, redactor=self._redactor)
        return store.render_history(task_id=str(task_id))

    async def _optimization_records(self, task_id: str) -> tuple[dict[str, object], ...]:
        if self._optimization_record_root is None:
            return ()
        store = OptimizationRecordStore(self._optimization_record_root, redactor=self._redactor)
        return store.list_records(task_id=str(task_id))

    async def _resolve_retry_base(
        self,
        *,
        plan: OptimizationPlan,
        retry_records: tuple[dict[str, object], ...],
    ) -> None:
        decision = plan.retry_decision
        if decision is None:
            raise StructuredOutputError("retry plans require retryDecision")
        if not retry_records:
            raise StructuredOutputError("retry history is empty")
        last = retry_records[-1]
        last_attempt = int(last.get("attempt", len(retry_records)))
        if decision.based_on_attempt != last_attempt:
            raise StructuredOutputError(
                f"retryDecision.basedOnAttempt must be the last attempt {last_attempt}"
            )
        if decision.mode == "continue" and decision.parent_attempt != last_attempt:
            raise StructuredOutputError(
                "continue retries must use the last attempt as parentAttempt"
            )
        if decision.parent_attempt > last_attempt:
            raise StructuredOutputError("retry parentAttempt cannot be in the future")
        if decision.parent_attempt == 0:
            self._candidate_base_workspace = None
            self._candidate_parent_candidate_id = None
            return
        source = next(
            (
                record
                for record in reversed(retry_records)
                if int(record.get("attempt", 0)) == decision.parent_attempt
            ),
            None,
        )
        if source is None:
            raise StructuredOutputError(
                f"retry parent attempt {decision.parent_attempt} was not found"
            )
        candidate_id = source.get("candidate_id")
        if not isinstance(candidate_id, str) or self._candidate_service is None:
            self._candidate_base_workspace = None
            self._candidate_parent_candidate_id = None
            return
        try:
            candidate = await self._candidate_service.get(candidate_id)
        except Exception as exc:
            raise StructuredOutputError(
                f"retry parent candidate {candidate_id} is unavailable: {exc}"
            ) from exc
        self._candidate_base_workspace = Path(candidate.workspace_ref)
        self._candidate_parent_candidate_id = str(candidate.id)

    async def _write_optimization_record(
        self,
        *,
        task_id: str,
        command: str,
        started_at: str,
        result: AgentRunResult | None,
        error: BaseException | None,
    ) -> None:
        if self._optimization_record_root is None:
            return
        task = await self._task_service.get_task(task_id)
        project = await self._project_service.get(task.project_id)
        layout = ProjectLayout.from_root(project.root_path)
        candidates = (
            await self._candidate_service.list_for_task(task.id)
            if self._candidate_service is not None
            else []
        )
        candidate = candidates[0] if candidates else None
        candidate_id = str(candidate.id) if candidate is not None else None
        changed_files: tuple[str, ...] = ()
        diff = ""
        if candidate is not None:
            try:
                repository = await GitRepository.discover(candidate.workspace_ref)
                snapshot = await repository.capture_snapshot(Path(candidate.workspace_ref))
                changed_files = await repository.changed_files(Path(candidate.workspace_ref))
                diff = snapshot.patch.decode(errors="replace")
            except Exception:
                changed_files = ()
                diff = ""
        correctness_runs = await self._correctness_service.list_for_task(task.id)
        correctness_run = next(
            (
                run
                for run in correctness_runs
                if run.target_kind == "candidate" and run.target_id == candidate_id
            ),
            None,
        )
        benchmark_runs = await self._benchmark_service.list_for_task(task.id)
        benchmark_run = next(
            (
                run
                for run in reversed(benchmark_runs)
                if run.target_kind == "candidate"
                and run.target_id == candidate_id
                and run.comparison_ref is not None
            ),
            None,
        )
        comparison = (
            await self._benchmark_service.read_comparison(benchmark_run)
            if benchmark_run is not None
            else {}
        )
        plan = _json_object(self._optimization_plan_text)
        retry_decision = plan.get("retryDecision") if isinstance(plan, dict) else None
        if not isinstance(retry_decision, dict):
            retry_decision = {}
        parent_attempt = int(retry_decision.get("parentAttempt", 0) or 0)
        prior_records = await self._optimization_records(str(task.id))
        parent_record = next(
            (
                record
                for record in reversed(prior_records)
                if int(record.get("attempt", 0)) == parent_attempt
            ),
            None,
        )
        current_improvement = (
            float(comparison.get("improvement_percent"))
            if isinstance(comparison, dict) and comparison.get("improvement_percent") is not None
            else None
        )
        parent_improvement = _optional_float(
            parent_record.get("improvement_percent") if parent_record is not None else None
        )
        prior_best = max(
            (
                record
                for record in prior_records
                if _optional_float(record.get("improvement_percent")) is not None
            ),
            key=lambda record: (
                _optional_float(record.get("improvement_percent"))
                if _optional_float(record.get("improvement_percent")) is not None
                else float("-inf")
            ),
            default=None,
        )
        best_improvement = _optional_float(
            prior_best.get("improvement_percent") if prior_best is not None else None
        )
        global_best = prior_best
        if current_improvement is not None and (
            best_improvement is None or current_improvement > best_improvement
        ):
            best_improvement = current_improvement
            global_best = {"attempt": len(prior_records) + 1}
        contract_hash = ""
        if layout.contract_path.is_file():
            contract_hash = hashlib.sha256(layout.contract_path.read_bytes()).hexdigest()
        outcomes = [
            {
                "status": outcome.status,
                "summary": outcome.summary,
                "findings": list(outcome.findings),
                "blockers": list(outcome.blockers),
            }
            for outcome in (result.outcomes if result is not None else ())
        ]
        payload = {
            "project_id": str(task.project_id),
            "command": command,
            "status": result.status if result is not None else "failed",
            "started_at": started_at,
            "completed_at": datetime.now(UTC).isoformat(),
            "objective": task.objective,
            "contract_hash": contract_hash,
            "completed_phases": list(result.completed_phases) if result is not None else [],
            "turns": result.turns if result is not None else 0,
            "tool_calls": result.tool_calls if result is not None else 0,
            "summary": result.summary if result is not None else str(error or ""),
            "outcomes": outcomes,
            "candidate_id": candidate_id,
            "candidate_status": candidate.status.value if candidate is not None else None,
            "changed_files": list(changed_files),
            "plan": plan,
            "retry_mode": retry_decision.get("mode"),
            "based_on_attempt": retry_decision.get("basedOnAttempt"),
            "parent_attempt": parent_attempt,
            "direction_id": retry_decision.get("directionId"),
            "direction_state": retry_decision.get("directionState", "active"),
            "preserve_changes": retry_decision.get("preserveChanges", []),
            "delta_vs_parent": (
                current_improvement - parent_improvement
                if current_improvement is not None and parent_improvement is not None
                else None
            ),
            "delta_vs_global_best": (
                current_improvement - best_improvement
                if current_improvement is not None and best_improvement is not None
                else None
            ),
            "global_best_attempt": (
                global_best.get("attempt") if isinstance(global_best, dict) else None
            ),
            "global_best_improvement": best_improvement,
            "diff": diff,
            "correctness": {
                "result_id": correctness_run.id if correctness_run is not None else None,
                "status": (correctness_run.status.value if correctness_run is not None else None),
                "failure_kind": (
                    correctness_run.failure_kind.value
                    if correctness_run is not None and correctness_run.failure_kind is not None
                    else None
                ),
            },
            "benchmark": comparison,
            "benchmark_valid": comparison.get("valid") if isinstance(comparison, dict) else None,
            "improvement_percent": (
                comparison.get("improvement_percent") if isinstance(comparison, dict) else None
            ),
            "model_log_dir": (
                str(self._model_call_logger.root) if self._model_call_logger is not None else None
            ),
            "error": (
                {"type": type(error).__name__, "message": str(error)} if error is not None else None
            ),
        }
        store = OptimizationRecordStore(self._optimization_record_root, redactor=self._redactor)
        await store.record(task_id=str(task.id), payload=payload)

    def _tool_schemas_for_phase(self, phase: TaskPhase) -> tuple[dict[str, object], ...]:
        schemas = self._tool_registry.provider_schemas()
        allowed_by_phase = {
            TaskPhase.ANALYZE: {
                "list_files",
                "read_file",
                "read_required_files",
                "search_code",
                "get_task_state",
                "read_resource",
            },
            TaskPhase.PLAN: {
                "submit_optimization_plan",
            },
            TaskPhase.GENERATE_CANDIDATE: {
                "create_candidate",
                "get_task_state",
            },
            TaskPhase.IMPLEMENT: {
                "apply_patch",
                "write_file",
                "edit_file",
                "run_candidate_check",
                "submit_phase_result",
                "get_candidate_diff",
                "get_task_state",
                "read_file",
            },
            TaskPhase.VERIFY: {
                "build",
                "run_correctness",
                "run_contract",
                "get_candidate_diff",
                "get_task_state",
                "read_file",
            },
            TaskPhase.BENCHMARK: {
                "run_benchmark",
                "get_candidate_diff",
                "get_task_state",
                "read_file",
            },
            TaskPhase.COMPARE: {
                "read_file",
                "get_task_state",
                "submit_phase_result",
            },
            TaskPhase.DECIDE: {
                "read_file",
                "get_task_state",
                "submit_phase_result",
            },
            TaskPhase.REPORT: {
                "read_file",
                "get_task_state",
                "submit_phase_result",
            },
        }
        allowed = allowed_by_phase.get(phase)
        if allowed is None:
            return schemas
        return tuple(schema for schema in schemas if schema.get("name") in allowed)

    async def _append_analysis_completed(
        self,
        *,
        task_id: str,
        phase: TaskPhase,
        report: AnalysisReport,
        coverage: ReadCoverage,
        ref: ArtifactRef,
    ) -> None:
        seq = await self._next_seq(task_id)
        await self._event_store.append(
            task_id,
            seq - 1,
            (
                _event(
                    task_id,
                    seq,
                    EventType.ANALYSIS_COMPLETED,
                    {
                        "phase": phase.value,
                        "summary": report.summary,
                        "coverage": coverage.payload(),
                        "optimization_candidates": [
                            candidate.model_dump(by_alias=True)
                            for candidate in report.optimization_candidates
                        ],
                        "profile_available": report.profile.get("available") is True,
                        "analysis_ref": _artifact_payload(ref),
                    },
                    artifact_refs=(ref,),
                ),
            ),
        )

    async def _append_plan_completed(
        self,
        *,
        task_id: str,
        plan: OptimizationPlan,
        ref: ArtifactRef,
    ) -> None:
        seq = await self._next_seq(task_id)
        await self._event_store.append(
            task_id,
            seq - 1,
            (
                _event(
                    task_id,
                    seq,
                    EventType.PLAN_COMPLETED,
                    {
                        "phase": TaskPhase.PLAN.value,
                        "summary": plan.summary,
                        "strategy": plan.strategy,
                        "step_count": len(plan.steps),
                        "protected_files": list(plan.protected_files),
                        "plan_ref": _artifact_payload(ref),
                    },
                    artifact_refs=(ref,),
                ),
            ),
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
            "analysis_report": self._analysis_report_text,
            "optimization_plan": self._optimization_plan_text,
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
    artifact_refs: tuple[ArtifactRef, ...] = (),
) -> EventEnvelope:
    return EventEnvelope(
        id=f"evt_{uuid4().hex}",
        aggregate_id=aggregate_id,
        seq=seq,
        type=event_type,
        payload=payload,
        artifact_refs=artifact_refs,
    )


def _json_object(value: str) -> dict[str, object] | None:
    if not value.strip():
        return None
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _optional_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
