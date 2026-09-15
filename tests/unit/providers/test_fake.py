from __future__ import annotations

import unittest

from algocode.domain.model import TaskPhase
from algocode.providers.fake import DeterministicFakeProvider, ScriptedFakeProvider
from algocode.providers.types import (
    FinishEvent,
    ModelRef,
    ModelRequest,
    ModelResponse,
    TextDelta,
    ToolCall,
    ToolCallDelta,
)


def _request(phase: str = "create") -> ModelRequest:
    return ModelRequest(
        request_id="req",
        model=ModelRef(provider_id="fake", model_id="test"),
        system="system",
        messages=(),
        metadata={"phase": phase},
    )


class FakeProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_scripted_provider_is_ordered(self) -> None:
        provider = ScriptedFakeProvider(
            (
                ModelResponse(
                    text="one",
                    tool_calls=(ToolCall(id="call", name="list_files"),),
                ),
                ModelResponse(text="two"),
            )
        )

        first = await provider.complete(_request())
        second = await provider.complete(_request())

        self.assertEqual(first.text, "one")
        self.assertEqual(first.tool_calls[0].name, "list_files")
        self.assertEqual(second.text, "two")

    async def test_scripted_provider_streams_events(self) -> None:
        provider = ScriptedFakeProvider(
            (
                ModelResponse(
                    text="hello",
                    tool_calls=(ToolCall(id="call", name="list_files"),),
                ),
            )
        )
        events = [event async for event in provider.stream(_request())]

        self.assertIsInstance(events[0], TextDelta)
        self.assertIsInstance(events[1], ToolCallDelta)
        self.assertIsInstance(events[-1], FinishEvent)

    async def test_deterministic_provider_inspects_first(self) -> None:
        provider = DeterministicFakeProvider()

        first = await provider.complete(_request(TaskPhase.CREATE.value))
        second = await provider.complete(_request(TaskPhase.CREATE.value))

        self.assertEqual(first.tool_calls[0].name, "list_files")
        self.assertEqual(second.tool_calls[0].name, "submit_phase_result")


if __name__ == "__main__":
    unittest.main()
