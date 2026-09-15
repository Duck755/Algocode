from __future__ import annotations

import unittest
from dataclasses import replace

from algocode.providers.errors import AuthenticationError
from algocode.providers.openai_compatible import OpenAICompatibleProvider
from algocode.providers.types import (
    FinishEvent,
    ModelRef,
    ModelRequest,
    TextDelta,
    ToolCallDelta,
    UsageEvent,
)
from tests.support.mock_openai import MockOpenAIServer


def _request(tools: tuple[dict[str, object], ...] = ()) -> ModelRequest:
    return ModelRequest(
        request_id="req",
        model=ModelRef(provider_id="mock", model_id="mock-model"),
        system="system",
        messages=(),
        tools=tools,
        timeout_seconds=5,
    )


class OpenAICompatibleProviderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.server = MockOpenAIServer()
        self.server.__enter__()
        self.provider = OpenAICompatibleProvider(
            provider_id="mock",
            base_url=self.server.base_url,
            api_key="test-key",
            model_id="fallback-model",
        )

    def tearDown(self) -> None:
        self.server.__exit__(None, None, None)

    def _enqueue_text_tool_usage(self) -> None:
        self.server.enqueue_sse(
            [
                {
                    "id": "chunk-1",
                    "choices": [{"delta": {"content": "Hel"}, "finish_reason": None}],
                },
                {
                    "id": "chunk-2",
                    "choices": [
                        {
                            "delta": {"content": "lo", "reasoning_content": "reason"},
                            "finish_reason": None,
                        }
                    ],
                },
                {
                    "id": "chunk-3",
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call-1",
                                        "function": {
                                            "name": "read_file",
                                            "arguments": '{"path":',
                                        },
                                    }
                                ]
                            },
                            "finish_reason": None,
                        }
                    ],
                },
                {
                    "id": "chunk-4",
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "function": {"arguments": '"main.py"}'},
                                    }
                                ]
                            },
                            "finish_reason": "tool_calls",
                        }
                    ],
                },
                {
                    "id": "chunk-5",
                    "choices": [],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                        "completion_tokens_details": {"reasoning_tokens": 2},
                    },
                },
            ]
        )

    async def test_complete_parses_text_tool_calls_and_usage(self) -> None:
        self._enqueue_text_tool_usage()
        request = replace(
            _request(
                (
                    {
                        "name": "read_file",
                        "description": "Read a file",
                        "input_schema": {"path": {"type": "string", "required": True}},
                    },
                )
            ),
            provider_options={"input_cost_per_million": 1.0, "output_cost_per_million": 2.0},
        )
        response = await self.provider.complete(request)
        self.assertEqual(response.usage.estimated_cost, 0.00002)

        self.assertEqual(response.text, "Hello")
        self.assertEqual(response.tool_calls[0].id, "call-1")
        self.assertEqual(response.tool_calls[0].name, "read_file")
        self.assertEqual(response.tool_calls[0].arguments, {"path": "main.py"})
        self.assertEqual(response.usage.input_tokens, 10)
        self.assertEqual(response.usage.output_tokens, 5)
        self.assertEqual(response.usage.reasoning_tokens, 2)

        payload = self.server.requests[0]
        self.assertTrue(payload["stream"])
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(
            payload["tools"][0]["function"]["parameters"]["required"],
            ["path"],
        )
        self.assertTrue(self.server.headers[0]["Authorization"].startswith("Bearer "))

    async def test_stream_emits_normalized_events(self) -> None:
        self._enqueue_text_tool_usage()
        events = [event async for event in self.provider.stream(_request())]

        self.assertIsInstance(events[0], TextDelta)
        self.assertIsInstance(events[1], ToolCallDelta)
        self.assertIsInstance(events[-2], UsageEvent)
        self.assertIsInstance(events[-1], FinishEvent)

    async def test_authentication_error_does_not_include_secret(self) -> None:
        self.server.enqueue_json(401, {"error": {"message": "invalid credentials"}})
        with self.assertRaises(AuthenticationError) as caught:
            await self.provider.complete(_request())

        self.assertNotIn("test-key", str(caught.exception))

    async def test_truncated_provider_output_retries(self) -> None:
        self.server.responses.append((200, "text/event-stream", "data: not-json\n\n"))
        self.server.enqueue_sse(
            [
                {
                    "id": "chunk",
                    "choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}],
                }
            ]
        )

        response = await self.provider.complete(_request())

        self.assertEqual(response.text, "ok")
        self.assertEqual(len(self.server.requests), 2)

    async def test_rate_limit_retries(self) -> None:
        self.server.enqueue_json(429, {"error": {"message": "rate limited"}})
        self.server.enqueue_sse(
            [
                {
                    "id": "chunk",
                    "choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}],
                }
            ]
        )
        response = await self.provider.complete(_request())

        self.assertEqual(response.text, "ok")
        self.assertEqual(len(self.server.requests), 2)


if __name__ == "__main__":
    unittest.main()
