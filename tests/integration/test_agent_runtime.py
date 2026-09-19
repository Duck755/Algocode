from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from algocode.bootstrap import build_context
from algocode.correctness.spec import CorrectnessCase, CorrectnessSpec
from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import CandidateStatus, TaskPhase, TaskStatus
from algocode.providers.errors import AuthenticationError, ContextOverflowError
from algocode.providers.fake import DeterministicFakeProvider
from algocode.providers.types import ModelRequest, ModelResponse, ToolCall
from algocode.runtime.agent import AgentRuntime
from algocode.runtime.optimization_record import OptimizationRecordStore
from algocode.runtime.planning import OptimizationPlan, RetryDecision
from algocode.tools import build_default_registry
from tests.support.git import init_git_repository


class AlwaysToolProvider:
    async def complete(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            tool_calls=(ToolCall(id="list", name="list_files", arguments={"pattern": "*"}),)
        )


class CoverageAnalysisProvider:
    def __init__(self) -> None:
        self.paths = ("main.py", ".algocode/config.yaml")
        self.index = 0

    async def complete(self, request: ModelRequest) -> ModelResponse:
        stage = request.metadata.get("stage")
        phase = str(request.metadata.get("phase", ""))
        if stage == "analysis_summary":
            return ModelResponse(
                text=json.dumps(
                    {
                        "summary": "Project analyzed from two read passes.",
                        "language": "python",
                        "files": [{"path": "main.py", "role": "algorithm"}],
                        "optimizationCandidates": [
                            {"id": "localize", "description": "Optimize the hot loop"}
                        ],
                    }
                )
            )
        if phase == "plan":
            return ModelResponse(
                tool_calls=(
                    ToolCall(
                        id="plan_result",
                        name="submit_optimization_plan",
                        arguments={
                            "summary": "Optimize the hot loop.",
                            "strategy": "Localize the expensive operation.",
                            "steps": [
                                {
                                    "id": "edit-main",
                                    "description": "Patch main.py.",
                                    "files": ["main.py"],
                                }
                            ],
                        },
                    ),
                )
            )
        if phase == "baseline":
            return ModelResponse(
                tool_calls=(
                    ToolCall(
                        id="baseline_result",
                        name="submit_phase_result",
                        arguments={
                            "phase": "baseline",
                            "status": "completed",
                            "summary": "baseline confirmed",
                        },
                    ),
                )
            )
        path = self.paths[self.index % len(self.paths)]
        self.index += 1
        return ModelResponse(
            tool_calls=(
                ToolCall(
                    id=f"analysis_read_{self.index}",
                    name="read_file",
                    arguments={"path": path},
                ),
            )
        )


class BenchmarkResumeProvider:
    def __init__(self) -> None:
        self.benchmark_requested = False

    async def complete(self, request: ModelRequest) -> ModelResponse:
        phase = str(request.metadata.get("phase", ""))
        if phase == "benchmark" and not self.benchmark_requested:
            self.benchmark_requested = True
            return ModelResponse(
                tool_calls=(
                    ToolCall(
                        id="benchmark_resume",
                        name="run_benchmark",
                        arguments={"spec": {"warmup": 0, "repeats": 1}},
                    ),
                )
            )
        return ModelResponse(
            tool_calls=(
                ToolCall(
                    id=f"submit_{phase}",
                    name="submit_phase_result",
                    arguments={
                        "phase": phase,
                        "status": "completed",
                        "summary": f"completed {phase}",
                    },
                ),
            )
        )


class RepeatingThenSubmitProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        if self.calls <= 4:
            return ModelResponse(
                tool_calls=(
                    ToolCall(
                        id=f"list_{self.calls}", name="list_files", arguments={"pattern": "*"}
                    ),
                )
            )
        return ModelResponse(
            tool_calls=(
                ToolCall(
                    id="submit_create",
                    name="submit_phase_result",
                    arguments={
                        "phase": "create",
                        "status": "completed",
                        "summary": "recovered from repeated reads",
                    },
                ),
            )
        )


class ReasoningToolProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.replayed_reasoning = ""

    async def complete(self, request: ModelRequest) -> ModelResponse:
        if self.calls == 0:
            self.calls += 1
            return ModelResponse(
                reasoning="hidden reasoning",
                tool_calls=(
                    ToolCall(
                        id="reasoning-list",
                        name="list_files",
                        arguments={"pattern": "*"},
                    ),
                ),
            )
        assistant_message = next(
            (
                message
                for message in reversed(request.messages)
                if message.role == "assistant" and message.tool_calls
            ),
            None,
        )
        if assistant_message is not None:
            self.replayed_reasoning = assistant_message.reasoning_content
        return ModelResponse(
            tool_calls=(
                ToolCall(
                    id="submit-create",
                    name="submit_phase_result",
                    arguments={
                        "phase": "create",
                        "status": "completed",
                        "summary": "completed with reasoning history",
                    },
                ),
            )
        )


class OverflowOnceProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        if self.calls == 1:
            raise ContextOverflowError("context window exceeded")
        return ModelResponse(
            tool_calls=(
                ToolCall(
                    id="submit_create",
                    name="submit_phase_result",
                    arguments={
                        "phase": "create",
                        "status": "completed",
                        "summary": "recovered from overflow",
                    },
                ),
            )
        )


class AuthenticationFailOnceProvider:
    def __init__(self) -> None:
        self.failed = False

    async def complete(self, request: ModelRequest) -> ModelResponse:
        if not self.failed:
            self.failed = True
            raise AuthenticationError("temporary authentication failure")
        return ModelResponse(text="unreachable")


class CandidateCreatingProvider:
    def __init__(self) -> None:
        self.created = False

    async def complete(self, request: ModelRequest) -> ModelResponse:
        phase = str(request.metadata.get("phase", ""))
        if phase == "generate_candidate" and not self.created:
            self.created = True
            return ModelResponse(
                tool_calls=(ToolCall(id="candidate", name="create_candidate", arguments={}),)
            )
        return ModelResponse(
            tool_calls=(
                ToolCall(
                    id=f"submit_{phase}",
                    name="submit_phase_result",
                    arguments={
                        "phase": phase,
                        "status": "completed",
                        "summary": f"completed {phase}",
                    },
                ),
            )
        )


class NoToolProvider:
    async def complete(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(text="verification failed and I am stopping")


class PatchThenSubmitWithoutCheckProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        if self.calls == 1:
            return ModelResponse(
                tool_calls=(
                    ToolCall(
                        id="patch_without_check",
                        name="apply_patch",
                        arguments={
                            "patch": (
                                "diff --git a/main.py b/main.py\n"
                                "--- a/main.py\n"
                                "+++ b/main.py\n"
                                "@@ -1,2 +1,2 @@\n"
                                " def solve():\n"
                                "-    return 42\n"
                                "+    return 43\n"
                            )
                        },
                    ),
                )
            )
        return ModelResponse(
            tool_calls=(
                ToolCall(
                    id="submit_without_check",
                    name="submit_phase_result",
                    arguments={
                        "phase": "implement",
                        "status": "completed",
                        "summary": "submitted without check",
                        "result": {"changedFiles": ["main.py"]},
                    },
                ),
            )
        )


class RepairAfterCandidateCheckFailureProvider:
    def __init__(self) -> None:
        self.step = 0
        self.saw_repair_context = False

    async def complete(self, request: ModelRequest) -> ModelResponse:
        phase = str(request.metadata.get("phase", ""))
        message_text = "\n".join(message.content for message in request.messages)
        if "repair-context" in message_text:
            self.saw_repair_context = True

        if phase != "implement":
            return ModelResponse(
                tool_calls=(
                    ToolCall(
                        id=f"submit_{phase}",
                        name="submit_phase_result",
                        arguments={
                            "phase": phase,
                            "status": "completed",
                            "summary": f"completed {phase}",
                        },
                    ),
                )
            )

        if self.step == 0:
            self.step += 1
            return ModelResponse(
                tool_calls=(
                    ToolCall(
                        id="break_candidate",
                        name="apply_patch",
                        arguments={
                            "patch": (
                                "diff --git a/main.py b/main.py\n"
                                "--- a/main.py\n"
                                "+++ b/main.py\n"
                                "@@ -1,2 +1,3 @@\n"
                                " def solve():\n"
                                "     return 42\n"
                                '+print("43")\n'
                            )
                        },
                    ),
                    ToolCall(
                        id="check_broken_candidate",
                        name="run_candidate_check",
                        arguments={},
                    ),
                )
            )
        if self.step == 1:
            self.step += 1
            return ModelResponse(
                tool_calls=(
                    ToolCall(
                        id="repair_candidate",
                        name="apply_patch",
                        arguments={
                            "patch": (
                                "diff --git a/main.py b/main.py\n"
                                "--- a/main.py\n"
                                "+++ b/main.py\n"
                                "@@ -1,3 +1,3 @@\n"
                                " def solve():\n"
                                "     return 42\n"
                                '-print("43")\n'
                                '+print("42")\n'
                            )
                        },
                    ),
                    ToolCall(
                        id="recheck_candidate",
                        name="run_candidate_check",
                        arguments={},
                    ),
                )
            )
        return ModelResponse(
            tool_calls=(
                ToolCall(
                    id="submit_repaired",
                    name="submit_phase_result",
                    arguments={
                        "phase": "implement",
                        "status": "completed",
                        "summary": "repaired candidate",
                        "result": {"changedFiles": ["main.py"]},
                    },
                ),
            )
        )


class InvalidImplementProvider:
    async def complete(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            tool_calls=(
                ToolCall(
                    id="invalid_implement",
                    name="submit_phase_result",
                    arguments={
                        "phase": "implement",
                        "status": "completed",
                        "summary": "claimed implementation",
                        "result": {"changedFiles": ["main.py"]},
                    },
                ),
            )
        )


class AgentRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.project_root = init_git_repository(
            self.root / "project",
            {"main.py": "def solve():\n    return 42\n"},
        )
        self.context = build_context(data_dir=self.root / "data")
        self.project = await self.context.project_service.register(
            self.project_root,
            write_config=True,
        )
        self.task = await self.context.task_service.create_task(
            "Optimize solver",
            project_id=self.project.id,
        )

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _runtime(self, provider, **overrides) -> AgentRuntime:
        return AgentRuntime(
            event_store=self.context.event_store,
            task_service=self.context.task_service,
            provider=provider,
            tool_registry=build_default_registry(),
            project_service=self.context.project_service,
            baseline_service=self.context.baseline_service,
            artifact_store=self.context.artifact_store,
            language_registry=self.context.language_registry,
            correctness_service=self.context.correctness_service,
            benchmark_service=self.context.benchmark_service,
            **overrides,
        )

    async def test_deterministic_fake_provider_completes_phase_machine(self) -> None:
        await self.context.baseline_service.capture(self.task.id)
        result = await self._runtime(CoverageAnalysisProvider()).run(
            self.task.id,
            stop_after=TaskPhase.BASELINE,
        )

        self.assertEqual(result.status, TaskStatus.COMPLETED.value)
        self.assertEqual(result.completed_phases[-1], TaskPhase.BASELINE.value)
        task = await self.context.task_service.get_task(self.task.id)
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        events = await self.context.event_store.read(str(self.task.id))
        event_types = {event.type for event in events}
        self.assertIn(EventType.TOOL_CALL_STARTED, event_types)
        self.assertIn(EventType.TOOL_CALL_COMPLETED, event_types)
        self.assertIn(EventType.AGENT_TURN_STARTED, event_types)
        self.assertIn(EventType.TASK_PHASE_CHANGED, event_types)
        self.assertIn(EventType.CONTEXT_ASSEMBLED, event_types)
        self.assertIn(EventType.TASK_COMPLETED, event_types)

    async def test_tool_budget_blocks_phase(self) -> None:
        result = await self._runtime(
            AlwaysToolProvider(),
            max_steps_per_phase=1,
            max_tool_calls_per_phase=1,
        ).run(self.task.id, stop_after=TaskPhase.CREATE)

        self.assertEqual(result.status, TaskStatus.WAITING_USER.value)
        self.assertIn("budget exhausted", result.summary)

    async def test_phase_tool_visibility_matrix(self) -> None:
        runtime = self._runtime(DeterministicFakeProvider())
        expected = {
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

        for phase, names in expected.items():
            actual = {str(schema["name"]) for schema in runtime._tool_schemas_for_phase(phase)}
            self.assertEqual(actual, names, phase.value)

    async def test_cancellation_is_durable(self) -> None:
        cancel = asyncio.Event()
        cancel.set()
        result = await self._runtime(
            DeterministicFakeProvider(),
            model_log_root=self.root / "model-logs",
        ).run(
            self.task.id,
            cancel_event=cancel,
        )

        self.assertEqual(result.status, TaskStatus.CANCELLED.value)
        events = await self.context.event_store.read(str(self.task.id))
        self.assertEqual(events[-2].type, EventType.AGENT_CANCELLED)
        self.assertEqual(events[-1].type, EventType.TASK_CANCELLED)

    async def test_runtime_records_model_calls_as_markdown(self) -> None:
        log_root = self.root / "model-logs"
        result = await self._runtime(
            DeterministicFakeProvider(),
            model_log_root=log_root,
        ).run(self.task.id, stop_after=TaskPhase.CREATE)

        self.assertEqual(result.status, TaskStatus.COMPLETED.value)
        files = sorted((log_root / str(self.task.id)).glob("*.md"))
        self.assertTrue(files)
        text = files[0].read_text(encoding="utf-8")
        self.assertIn("## System Prompt", text)
        self.assertIn("## Input Messages", text)
        self.assertIn("list_files", text)
        self.assertIn("Inspecting the workspace", text)
        self.assertIn("provider did not return reasoning content", text)

    async def test_no_progress_warning_allows_model_to_recover(self) -> None:
        provider = RepeatingThenSubmitProvider()
        result = await self._runtime(provider).run(
            self.task.id,
            stop_after=TaskPhase.CREATE,
        )

        self.assertEqual(result.status, TaskStatus.COMPLETED.value)
        events = await self.context.event_store.read(str(self.task.id))
        summaries = [event.payload.get("summary", "") for event in events]
        self.assertTrue(any("STOP REPEATING" in summary for summary in summaries))

    async def test_reasoning_content_is_replayed_in_tool_history(self) -> None:
        provider = ReasoningToolProvider()
        result = await self._runtime(provider).run(
            self.task.id,
            stop_after=TaskPhase.CREATE,
        )

        self.assertEqual(result.status, TaskStatus.COMPLETED.value)
        self.assertEqual(provider.replayed_reasoning, "hidden reasoning")

    async def test_analyze_auto_completes_after_two_read_passes(self) -> None:
        events = await self.context.event_store.read(str(self.task.id))
        seq = events[-1].seq + 1
        await self.context.event_store.append(
            str(self.task.id),
            seq - 1,
            (
                EventEnvelope(
                    id="evt_analysis_phase",
                    aggregate_id=str(self.task.id),
                    seq=seq,
                    type=EventType.TASK_PHASE_CHANGED,
                    payload={"current_phase": "analyze", "status": "running"},
                ),
            ),
        )

        result = await self._runtime(CoverageAnalysisProvider()).run(
            self.task.id,
            stop_after=TaskPhase.ANALYZE,
        )

        self.assertEqual(result.status, TaskStatus.COMPLETED.value)
        events = await self.context.event_store.read(str(self.task.id))
        self.assertIn(EventType.ANALYSIS_COMPLETED, [event.type for event in events])
        analysis_events = [
            event
            for event in events
            if event.type is EventType.ANALYSIS_COMPLETED
        ]
        self.assertEqual(len(analysis_events), 1)
        self.assertTrue(analysis_events[0].payload.get("profile_available"))
        reads = [
            event
            for event in events
            if event.type is EventType.TOOL_CALL_COMPLETED
            and event.payload.get("name") == "read_file"
        ]
        self.assertEqual(len(reads), 3)

    async def test_plan_is_runtime_managed_and_persisted(self) -> None:
        await self.context.baseline_service.capture(self.task.id)
        events = await self.context.event_store.read(str(self.task.id))
        seq = events[-1].seq + 1
        await self.context.event_store.append(
            str(self.task.id),
            seq - 1,
            (
                EventEnvelope(
                    id="evt_plan_phase",
                    aggregate_id=str(self.task.id),
                    seq=seq,
                    type=EventType.TASK_PHASE_CHANGED,
                    payload={"current_phase": "analyze", "status": "running"},
                ),
            ),
        )

        result = await self._runtime(CoverageAnalysisProvider()).run(
            self.task.id,
            stop_after=TaskPhase.PLAN,
        )

        self.assertEqual(result.status, TaskStatus.COMPLETED.value)
        self.assertIn(TaskPhase.PLAN.value, result.completed_phases)
        events = await self.context.event_store.read(str(self.task.id))
        plan_events = [event for event in events if event.type is EventType.PLAN_COMPLETED]
        self.assertEqual(len(plan_events), 1)
        self.assertEqual(plan_events[0].payload["step_count"], 1)
        self.assertIn(
            "submit_optimization_plan",
            [
                event.payload.get("name")
                for event in events
                if event.type is EventType.TOOL_CALL_STARTED
                and event.payload.get("phase") == TaskPhase.PLAN.value
            ],
        )

    async def test_benchmark_resume_recovers_persisted_correctness(self) -> None:
        await self.context.baseline_service.capture(self.task.id)
        spec = CorrectnessSpec(
            mode="cases",
            comparison="line-trim",
            cases=(CorrectnessCase(id="output", expected_output=""),),
        )
        await self.context.correctness_service.run_baseline(self.task.id, spec)
        candidate = await self.context.candidate_service.create(self.task.id)
        _, correctness = await self.context.correctness_service.run_target(
            self.task.id,
            spec,
            target_kind="candidate",
            target_id=str(candidate.id),
            workspace_ref=candidate.workspace_ref,
        )
        self.assertTrue(correctness.passed)

        events = await self.context.event_store.read(str(self.task.id))
        seq = events[-1].seq + 1
        await self.context.event_store.append(
            str(self.task.id),
            seq - 1,
            (
                EventEnvelope(
                    id="evt_resume_benchmark",
                    aggregate_id=str(self.task.id),
                    seq=seq,
                    type=EventType.TASK_PHASE_CHANGED,
                    payload={"current_phase": "benchmark", "status": "running"},
                ),
            ),
        )

        result = await self._runtime(
            BenchmarkResumeProvider(),
            candidate_service=self.context.candidate_service,
            database=self.context.database,
        ).run(self.task.id, stop_after=TaskPhase.BENCHMARK)

        self.assertEqual(result.status, TaskStatus.COMPLETED.value)
        events = await self.context.event_store.read(str(self.task.id))
        benchmark_results = [
            event
            for event in events
            if event.type is EventType.TOOL_CALL_COMPLETED
            and event.payload.get("name") == "run_benchmark"
        ]
        self.assertEqual(benchmark_results[-1].payload["status"], "success")

    async def test_verify_does_not_complete_after_correctness_failure(self) -> None:
        await self.context.baseline_service.capture(self.task.id)
        candidate = await self.context.candidate_service.create(self.task.id)
        spec = CorrectnessSpec(
            mode="cases",
            comparison="line-trim",
            cases=(CorrectnessCase(id="output", expected_output="wrong"),),
        )
        _, correctness = await self.context.correctness_service.run_target(
            self.task.id,
            spec,
            target_kind="candidate",
            target_id=str(candidate.id),
            workspace_ref=candidate.workspace_ref,
        )
        self.assertFalse(correctness.passed)

        events = await self.context.event_store.read(str(self.task.id))
        seq = events[-1].seq + 1
        await self.context.event_store.append(
            str(self.task.id),
            seq - 1,
            (
                EventEnvelope(
                    id="evt_verify_phase",
                    aggregate_id=str(self.task.id),
                    seq=seq,
                    type=EventType.TASK_PHASE_CHANGED,
                    payload={"current_phase": "verify", "status": "running"},
                ),
            ),
        )

        result = await self._runtime(
            NoToolProvider(),
            candidate_service=self.context.candidate_service,
            database=self.context.database,
        ).run(self.task.id, stop_after=TaskPhase.VERIFY)

        self.assertEqual(result.status, TaskStatus.WAITING_USER.value)
        candidates = await self.context.candidate_service.list_for_task(self.task.id)
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].status, CandidateStatus.GENERATED)
        self.assertNotIn(TaskPhase.VERIFY.value, result.completed_phases)

    async def test_context_overflow_compacts_and_retries(self) -> None:
        provider = OverflowOnceProvider()
        result = await self._runtime(provider).run(
            self.task.id,
            stop_after=TaskPhase.CREATE,
        )

        self.assertEqual(result.status, TaskStatus.COMPLETED.value)
        self.assertEqual(provider.calls, 2)
        events = await self.context.event_store.read(str(self.task.id))
        self.assertIn(EventType.CONTEXT_COMPACTED, [event.type for event in events])

    async def test_provider_failure_can_resume_safely(self) -> None:
        with self.assertRaises(AuthenticationError):
            await self._runtime(AuthenticationFailOnceProvider()).run(
                self.task.id,
                stop_after=TaskPhase.CREATE,
            )

        result = await self._runtime(DeterministicFakeProvider()).run(
            self.task.id,
            stop_after=TaskPhase.CREATE,
        )
        events = await self.context.event_store.read(str(self.task.id))

        self.assertEqual(result.status, TaskStatus.COMPLETED.value)
        self.assertEqual([event.seq for event in events], list(range(1, len(events) + 1)))

    async def test_implement_submit_requires_validated_patch(self) -> None:
        await self.context.baseline_service.capture(self.task.id)
        await self.context.candidate_service.create(self.task.id)
        events = await self.context.event_store.read(str(self.task.id))
        seq = events[-1].seq + 1
        await self.context.event_store.append(
            str(self.task.id),
            seq - 1,
            (
                EventEnvelope(
                    id="evt_implement_phase",
                    aggregate_id=str(self.task.id),
                    seq=seq,
                    type=EventType.TASK_PHASE_CHANGED,
                    payload={"current_phase": "implement", "status": "running"},
                ),
            ),
        )

        result = await self._runtime(
            InvalidImplementProvider(),
            candidate_service=self.context.candidate_service,
            max_steps_per_phase=3,
        ).run(self.task.id, stop_after=TaskPhase.IMPLEMENT)

        self.assertEqual(result.status, TaskStatus.WAITING_USER.value)
        events = await self.context.event_store.read(str(self.task.id))
        summaries = [
            event.payload.get("summary", "")
            for event in events
            if event.type is EventType.TOOL_CALL_COMPLETED
            and event.payload.get("name") == "submit_phase_result"
        ]
        self.assertTrue(any("apply_patch must succeed" in summary for summary in summaries))

    async def test_implement_requires_candidate_check_before_submit(self) -> None:
        await self.context.baseline_service.capture(self.task.id)
        candidate = await self.context.candidate_service.create(self.task.id)
        oracle_dir = Path(candidate.workspace_ref) / ".algocode" / "oracle"
        oracle_dir.mkdir(parents=True)
        (oracle_dir / "correctness.yaml").write_text(
            "schema_version: 1\nmode: cases\ncomparison: line-trim\ncases: []\n",
            encoding="utf-8",
        )
        events = await self.context.event_store.read(str(self.task.id))
        seq = events[-1].seq + 1
        await self.context.event_store.append(
            str(self.task.id),
            seq - 1,
            (
                EventEnvelope(
                    id="evt_implement_requires_check",
                    aggregate_id=str(self.task.id),
                    seq=seq,
                    type=EventType.TASK_PHASE_CHANGED,
                    payload={"current_phase": "implement", "status": "running"},
                ),
            ),
        )

        result = await self._runtime(
            PatchThenSubmitWithoutCheckProvider(),
            candidate_service=self.context.candidate_service,
            max_steps_per_phase=3,
        ).run(self.task.id, stop_after=TaskPhase.IMPLEMENT)

        self.assertEqual(result.status, TaskStatus.WAITING_USER.value)
        events = await self.context.event_store.read(str(self.task.id))
        summaries = [
            event.payload.get("summary", "")
            for event in events
            if event.type is EventType.TOOL_CALL_COMPLETED
        ]
        self.assertTrue(any("run_candidate_check" in summary for summary in summaries))

    async def test_candidate_check_failure_injects_repair_context_and_recovers(self) -> None:
        await self.context.baseline_service.capture(self.task.id)
        candidate = await self.context.candidate_service.create(self.task.id)
        oracle_dir = Path(candidate.workspace_ref) / ".algocode" / "oracle"
        oracle_dir.mkdir(parents=True)
        (oracle_dir / "correctness.yaml").write_text(
            "schema_version: 1\n"
            "mode: cases\n"
            "comparison: line-trim\n"
            "cases:\n"
            "  - id: output\n"
            "    expected_output: '42'\n",
            encoding="utf-8",
        )
        events = await self.context.event_store.read(str(self.task.id))
        seq = events[-1].seq + 1
        await self.context.event_store.append(
            str(self.task.id),
            seq - 1,
            (
                EventEnvelope(
                    id="evt_implement_repair_context",
                    aggregate_id=str(self.task.id),
                    seq=seq,
                    type=EventType.TASK_PHASE_CHANGED,
                    payload={"current_phase": "implement", "status": "running"},
                ),
            ),
        )

        provider = RepairAfterCandidateCheckFailureProvider()
        log_root = self.root / "model-logs"
        result = await self._runtime(
            provider,
            candidate_service=self.context.candidate_service,
            database=self.context.database,
            model_log_root=log_root,
            max_steps_per_phase=8,
            max_tool_calls_per_phase=12,
        ).run(self.task.id, stop_after=TaskPhase.IMPLEMENT)

        self.assertEqual(result.status, TaskStatus.COMPLETED.value)
        self.assertIn(TaskPhase.IMPLEMENT.value, result.completed_phases)
        self.assertTrue(provider.saw_repair_context)
        self.assertEqual(
            (Path(candidate.workspace_ref) / "main.py").read_text(encoding="utf-8").strip(),
            'def solve():\n    return 42\nprint("42")',
        )

        memory_path = self.root / "repair-memory" / str(self.task.id) / "attempts.json"
        memory = json.loads(memory_path.read_text(encoding="utf-8"))
        self.assertEqual(len(memory["attempts"]), 1)
        failure_details = memory["attempts"][0]["failure"]["structured"]["failure_details"]
        self.assertEqual(failure_details[0]["actual_output"].strip(), "43")
        self.assertEqual(failure_details[0]["expected_output"].strip(), "42")

    async def test_runtime_persists_optimization_record(self) -> None:
        result = await self._runtime(
            DeterministicFakeProvider(),
            model_log_root=self.root / "model-logs",
        ).run(
            self.task.id,
            stop_after=TaskPhase.CREATE,
        )

        self.assertEqual(result.status, TaskStatus.COMPLETED.value)
        records_dir = self.root / "optimization-records" / str(self.task.id)
        record_files = sorted(records_dir.glob("*.json"))
        self.assertEqual(len(record_files), 1)
        payload = json.loads(record_files[0].read_text(encoding="utf-8"))
        self.assertEqual(payload["command"], "optimize")
        self.assertEqual(payload["status"], TaskStatus.COMPLETED.value)
        self.assertIn(TaskPhase.CREATE.value, payload["completed_phases"])

    async def test_retry_boundary_excludes_old_candidates_and_injects_history(self) -> None:
        await self.context.baseline_service.capture(self.task.id)
        candidate = await self.context.candidate_service.create(self.task.id)
        await OptimizationRecordStore(self.root / "optimization-records").record(
            task_id=str(self.task.id),
            payload={
                "command": "optimize",
                "status": "completed",
                "summary": "previous attempt",
                "candidate_id": str(candidate.id),
                "plan": {"summary": "previous plan", "strategy": "previous strategy"},
            },
        )
        events = await self.context.event_store.read(str(self.task.id))
        seq = events[-1].seq + 1
        await self.context.event_store.append(
            str(self.task.id),
            seq - 1,
            (
                EventEnvelope(
                    id="evt_retry_requested",
                    aggregate_id=str(self.task.id),
                    seq=seq,
                    type=EventType.TASK_RETRY_REQUESTED,
                    payload={"retry_id": "retry_test"},
                ),
            ),
        )

        runtime = self._runtime(
            DeterministicFakeProvider(),
            candidate_service=self.context.candidate_service,
            model_log_root=self.root / "model-logs",
        )
        retry_candidates = await runtime._retry_candidate_ids(str(self.task.id))
        history = await runtime._optimization_history(str(self.task.id))

        self.assertEqual(retry_candidates, set())
        self.assertIn("previous plan", history)
        self.assertNotIn(str(candidate.id), retry_candidates or set())
        plan = OptimizationPlan(
            summary="continue",
            strategy="continue from the previous attempt",
            steps=[{"id": "s1", "description": "Continue."}],
            retry_decision=RetryDecision(
                mode="continue",
                based_on_attempt=1,
                parent_attempt=1,
                direction_id="previous-direction",
                reason="not exhausted",
            ),
        )
        await runtime._resolve_retry_base(
            plan=plan,
            retry_records=await runtime._optimization_records(str(self.task.id)),
        )
        self.assertEqual(runtime._candidate_base_workspace, Path(candidate.workspace_ref))

    async def test_provider_can_create_candidate_workspace(self) -> None:
        await self.context.baseline_service.capture(self.task.id)
        events = await self.context.event_store.read(str(self.task.id))
        seq = events[-1].seq + 1
        await self.context.event_store.append(
            str(self.task.id),
            seq - 1,
            (
                EventEnvelope(
                    id="evt_generate_candidate_phase",
                    aggregate_id=str(self.task.id),
                    seq=seq,
                    type=EventType.TASK_PHASE_CHANGED,
                    payload={"current_phase": "generate_candidate", "status": "running"},
                ),
            ),
        )
        result = await self._runtime(
            CandidateCreatingProvider(),
            candidate_service=self.context.candidate_service,
        ).run(self.task.id, stop_after=TaskPhase.GENERATE_CANDIDATE)

        self.assertEqual(result.status, TaskStatus.COMPLETED.value)
        candidates = await self.context.candidate_service.list_for_task(self.task.id)
        self.assertEqual(len(candidates), 1)
        events = await self.context.event_store.read(str(self.task.id))
        self.assertIn(EventType.CANDIDATE_CREATED, [event.type for event in events])


if __name__ == "__main__":
    unittest.main()
