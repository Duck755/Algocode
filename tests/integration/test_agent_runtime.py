from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from algocode.bootstrap import build_context
from algocode.domain.events import EventType
from algocode.domain.model import TaskPhase, TaskStatus
from algocode.providers.errors import AuthenticationError, ContextOverflowError
from algocode.providers.fake import DeterministicFakeProvider
from algocode.providers.types import ModelRequest, ModelResponse, ToolCall
from algocode.runtime.agent import AgentRuntime
from algocode.tools import build_default_registry
from tests.support.git import init_git_repository


class AlwaysToolProvider:
    async def complete(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            tool_calls=(ToolCall(id="list", name="list_files", arguments={"pattern": "*"}),)
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
        result = await self._runtime(DeterministicFakeProvider()).run(
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

    async def test_cancellation_is_durable(self) -> None:
        cancel = asyncio.Event()
        cancel.set()
        result = await self._runtime(DeterministicFakeProvider()).run(
            self.task.id,
            cancel_event=cancel,
        )

        self.assertEqual(result.status, TaskStatus.CANCELLED.value)
        events = await self.context.event_store.read(str(self.task.id))
        self.assertEqual(events[-2].type, EventType.AGENT_CANCELLED)
        self.assertEqual(events[-1].type, EventType.TASK_CANCELLED)

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

    async def test_provider_can_create_candidate_workspace(self) -> None:
        await self.context.baseline_service.capture(self.task.id)
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
