"""Isolated evaluation harness for agent runs."""

from __future__ import annotations

import statistics
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from algocode.benchmark.environment import compute_environment_hash
from algocode.benchmark.spec import BenchmarkSpec
from algocode.bootstrap import build_context
from algocode.config import compute_config_hash
from algocode.correctness.spec import CorrectnessSpec
from algocode.domain.events import EventType
from algocode.domain.model import CandidateStatus, CorrectnessStatus, TaskPhase, TaskStatus
from algocode.eval.provider import PhaseScriptedProvider
from algocode.eval.types import EvalTask, EvalTaskResult, ExpectedBehavior
from algocode.process_output import run_text
from algocode.providers.fake import DeterministicFakeProvider
from algocode.providers.types import ModelRef
from algocode.runtime.agent import AgentRunResult, AgentRuntime

ProviderFactory = Callable[[EvalTask, str | None], object]


class EvalHarness:
    """Run one evaluation task in a temporary Git repository and data directory."""

    def __init__(
        self,
        provider_factory: ProviderFactory,
        provider_name: str,
        model: ModelRef | None = None,
    ) -> None:
        self.provider_factory = provider_factory
        self.provider_name = provider_name
        self.model = model or ModelRef(provider_id="fake", model_id="deterministic")

    def default_provider_factory(self, task: EvalTask, candidate_id: str | None):
        return PhaseScriptedProvider(task, candidate_id)

    async def run_task(self, task: EvalTask) -> EvalTaskResult:
        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix=f"algocode-eval-{task.id}-") as directory:
            root = Path(directory)
            project_root = root / "project"
            _create_repository(project_root, task.files)
            data_dir = root / "data"
            context = build_context(project_root=project_root, data_dir=data_dir)
            project = await context.project_service.register(project_root, write_config=True)
            agent_task = await context.task_service.create_task(
                task.objective,
                project_id=project.id,
            )
            await context.baseline_service.capture(agent_task.id)
            correctness_spec = (
                CorrectnessSpec.model_validate(task.correctness_spec)
                if task.correctness_spec
                else None
            )
            benchmark_spec = (
                BenchmarkSpec.model_validate(task.benchmark_spec) if task.benchmark_spec else None
            )
            if correctness_spec is not None:
                await context.correctness_service.run_baseline(agent_task.id, correctness_spec)
            if benchmark_spec is not None:
                await context.benchmark_service.run_baseline(agent_task.id, benchmark_spec)

            candidate = None
            if task.candidate_patch is not None:
                candidate = await context.candidate_service.create(agent_task.id)

            provider = self.provider_factory(task, str(candidate.id) if candidate else None)
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
                max_steps_per_phase=task.max_steps,
                max_tool_calls_per_phase=task.max_tool_calls,
                database=context.database,
                candidate_service=context.candidate_service,
                resource_provider=context.resource_provider,
                redactor=context.secret_redactor,
                context_window=128_000,
                config_hash=compute_config_hash(context.config),
                policy_hash=context.policy_engine.hash(),
                model=self.model,
                model_log_root=context.data_dir / "model-logs",
                protected_files=task.protected_files
                or (
                    "tests/",
                    "oracle/",
                    "generator/",
                    "hidden-tests/",
                    "benchmarks/",
                    ".algocode.yaml",
                ),
            )
            first_result: AgentRunResult | None = None
            if task.expected_behavior is ExpectedBehavior.RECOVERY:
                first_result = await runtime.run(
                    agent_task.id,
                    stop_after=TaskPhase.ANALYZE,
                )
                recovery_runtime = AgentRuntime(
                    event_store=context.event_store,
                    task_service=context.task_service,
                    provider=DeterministicFakeProvider(),
                    tool_registry=context.tool_registry,
                    project_service=context.project_service,
                    baseline_service=context.baseline_service,
                    artifact_store=context.artifact_store,
                    language_registry=context.language_registry,
                    correctness_service=context.correctness_service,
                    benchmark_service=context.benchmark_service,
                    database=context.database,
                    candidate_service=context.candidate_service,
                    resource_provider=context.resource_provider,
                    redactor=context.secret_redactor,
                    context_window=128_000,
                    config_hash=compute_config_hash(context.config),
                    policy_hash=context.policy_engine.hash(),
                    model=self.model,
                    model_log_root=context.data_dir / "model-logs",
                    protected_files=task.protected_files,
                )
                final_result = await recovery_runtime.run(
                    agent_task.id,
                    stop_after=TaskPhase.GENERATE_CANDIDATE,
                )
            else:
                stop_after = (
                    TaskPhase.BASELINE
                    if task.expected_behavior is ExpectedBehavior.NO_OPTIMIZATION
                    else TaskPhase.REPORT
                )
                final_result = await runtime.run(
                    agent_task.id,
                    candidate_workspace=Path(candidate.workspace_ref) if candidate else None,
                    candidate_id=str(candidate.id) if candidate else None,
                    stop_after=stop_after,
                )

            events = await context.event_store.read(str(agent_task.id))
            task_after = await context.task_service.get_task(agent_task.id)
            candidates = await context.candidate_service.list_for_task(agent_task.id)
            correctness_runs = await context.correctness_service.list_for_task(agent_task.id)
            benchmark_runs = await context.benchmark_service.list_for_task(agent_task.id)
            passed, actual, message = self._grade(
                task,
                first_result,
                final_result,
                task_after.status,
                candidates,
                correctness_runs,
                benchmark_runs,
                events,
            )
            metrics = _metrics(
                final_result,
                first_result,
                events,
                compute_environment_hash(project_root),
                len(candidates),
                correctness_runs,
                benchmark_runs,
                task.expected_behavior,
            )
            return EvalTaskResult(
                task_id=task.id,
                passed=passed,
                expected_behavior=task.expected_behavior.value,
                actual_behavior=actual,
                duration_seconds=time.perf_counter() - started,
                turns=final_result.turns + (first_result.turns if first_result else 0),
                tool_calls=final_result.tool_calls
                + (first_result.tool_calls if first_result else 0),
                metrics=metrics,
                message=message,
            )

    def _grade(
        self,
        task: EvalTask,
        first_result: AgentRunResult | None,
        final_result: AgentRunResult,
        task_status: TaskStatus,
        candidates,
        correctness_runs,
        benchmark_runs,
        events,
    ) -> tuple[bool, str, str]:
        if task.expected_behavior is ExpectedBehavior.NO_OPTIMIZATION:
            passed = task_status is TaskStatus.COMPLETED and not candidates
            return passed, "no_optimization", "" if passed else "expected no candidate"
        if task.expected_behavior is ExpectedBehavior.OPTIMIZATION:
            candidate = candidates[-1] if candidates else None
            correctness_passed = any(
                run.target_kind == "candidate" and run.status is CorrectnessStatus.PASSED
                for run in correctness_runs
            )
            benchmark_valid = any(run.target_kind == "candidate" for run in benchmark_runs)
            positive_improvement = any(
                event.type is EventType.COMPARISON_PRODUCED
                and isinstance(event.payload.get("comparison"), dict)
                and float(event.payload["comparison"].get("improvement_percent", 0.0)) > 0
                for event in events
            )
            passed = (
                task_status is TaskStatus.COMPLETED
                and candidate is not None
                and candidate.status
                in {CandidateStatus.VERIFIED, CandidateStatus.SELECTED, CandidateStatus.APPLIED}
                and correctness_passed
                and benchmark_valid
                and positive_improvement
            )
            return (
                passed,
                "optimization",
                "" if passed else "candidate verification or benchmark evidence missing",
            )
        if task.expected_behavior is ExpectedBehavior.POLICY_DENY:
            denied = any(
                event.type is EventType.TOOL_CALL_COMPLETED
                and event.payload.get("name") == "apply_patch"
                and event.payload.get("status") == "error"
                and "protected" in str(event.payload.get("summary", "")).lower()
                for event in events
            )
            changed = any(
                event.type is EventType.TOOL_CALL_COMPLETED
                and event.payload.get("name") == "apply_patch"
                and event.payload.get("status") == "success"
                for event in events
            )
            passed = denied and not changed
            return passed, "policy_deny", "" if passed else "protected patch was not denied"
        if task.expected_behavior is ExpectedBehavior.RECOVERY:
            passed = (
                first_result is not None
                and first_result.status in {TaskStatus.WAITING_USER.value, TaskStatus.FAILED.value}
                and final_result.status == TaskStatus.COMPLETED.value
            )
            return passed, "recovery", "" if passed else "agent did not recover"
        if task.expected_behavior is ExpectedBehavior.REJECT:
            passed = not any(
                run.target_kind == "candidate" and run.comparison_ref is not None
                for run in benchmark_runs
            )
            return passed, "reject", "" if passed else "unexpected beneficial candidate"
        return False, "unknown", "unsupported expected behavior"


def _create_repository(root: Path, files: dict[str, str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for relative_path, content in files.items():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    _run(root, "git", "init", "-q")
    _run(root, "git", "config", "user.email", "algocode-eval@example.test")
    _run(root, "git", "config", "user.name", "Algocode Eval")
    _run(root, "git", "add", ".")
    _run(root, "git", "commit", "-q", "-m", "initial")


def _run(root: Path, *command: str) -> None:
    run_text(command, cwd=root, check=True, capture_output=True)


def _metrics(
    final_result: AgentRunResult,
    first_result: AgentRunResult | None,
    events,
    environment_hash: str,
    candidate_count: int,
    correctness_runs,
    benchmark_runs,
    expected_behavior: ExpectedBehavior,
) -> dict[str, float | int | str | None]:
    comparison_payloads = [
        event.payload.get("comparison", {})
        for event in events
        if event.type is EventType.COMPARISON_PRODUCED
    ]
    speedups = [
        float(payload["improvement_percent"])
        for payload in comparison_payloads
        if isinstance(payload, dict) and "improvement_percent" in payload
    ]
    valid_comparisons = [
        payload
        for payload in comparison_payloads
        if isinstance(payload, dict) and payload.get("valid") is True
    ]
    beneficial_comparisons = [
        payload
        for payload in valid_comparisons
        if float(payload.get("improvement_percent", 0.0)) > 0
    ]
    input_tokens = sum(
        int(event.payload.get("input_tokens", 0))
        for event in events
        if event.type is EventType.AGENT_TURN_COMPLETED
    )
    output_tokens = sum(
        int(event.payload.get("output_tokens", 0))
        for event in events
        if event.type is EventType.AGENT_TURN_COMPLETED
    )
    build_events = [
        event
        for event in events
        if event.type is EventType.TOOL_CALL_COMPLETED and event.payload.get("name") == "build"
    ]
    build_pass_rate = (
        sum(1 for event in build_events if event.payload.get("status") == "success")
        / len(build_events)
        if build_events
        else 1.0
    )
    accepted_candidate = any(
        event.type is EventType.DECISION_MADE and event.payload.get("outcome") == "accepted"
        for event in events
    )
    negative_expected = expected_behavior in {
        ExpectedBehavior.NO_OPTIMIZATION,
        ExpectedBehavior.POLICY_DENY,
        ExpectedBehavior.REJECT,
    }
    false_accept_rate = 1.0 if negative_expected and accepted_candidate else 0.0
    false_reject_rate = (
        1.0 if expected_behavior is ExpectedBehavior.OPTIMIZATION and candidate_count == 0 else 0.0
    )
    return {
        "build_pass_rate": build_pass_rate,
        "correctness_pass_rate": (
            sum(1 for run in correctness_runs if run.status is CorrectnessStatus.PASSED)
            / len(correctness_runs)
            if correctness_runs
            else 0.0
        ),
        "benchmark_validity_rate": (
            sum(
                1
                for run in benchmark_runs
                if run.target_kind == "candidate" and run.comparison_ref is not None
            )
            / max(1, candidate_count)
            if candidate_count
            else 0.0
        ),
        "optimization_acceptance_rate": (
            len(beneficial_comparisons) / max(1, candidate_count) if candidate_count else 0.0
        ),
        "false_accept_rate": false_accept_rate,
        "false_reject_rate": false_reject_rate,
        "median_speedup": statistics.median(speedups) if speedups else 0.0,
        "cost_per_accepted_candidate": 0.0,
        "recovery_success_rate": (
            1.0 if first_result and final_result.status == "completed" else 0.0
        ),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "candidate_count": candidate_count,
        "environment_hash": environment_hash,
    }
