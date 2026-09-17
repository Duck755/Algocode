from __future__ import annotations

import unittest
from dataclasses import replace

from algocode.providers.anthropic import AnthropicProvider
from algocode.providers.types import Message, ModelRef, ModelRequest, ToolCall
from tests.support.mock_openai import MockOpenAIServer


def _request() -> ModelRequest:
    return ModelRequest(
        request_id="req",
        model=ModelRef(provider_id="anthropic", model_id="claude-test"),
        system="system prompt",
        messages=(Message(role="user", content="hello"),),
        timeout_seconds=5,
    )


class AnthropicProviderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.server = MockOpenAIServer()
        self.server.__enter__()
        self.provider = AnthropicProvider(
            provider_id="anthropic",
            base_url=self.server.base_url,
            api_key="test-key",
            model_id="claude-test",
        )

    def tearDown(self) -> None:
        self.server.__exit__(None, None, None)

    async def test_complete_parses_text_usage_and_headers(self) -> None:
        self.server.enqueue_json(
            200,
            {
                "id": "msg-1",
                "content": [{"type": "text", "text": "hello"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

        response = await self.provider.complete(_request())

        self.assertEqual(response.text, "hello")
        self.assertEqual(response.usage.input_tokens, 10)
        self.assertEqual(response.usage.output_tokens, 5)
        headers = {key.lower(): value for key, value in self.server.headers[0].items()}
        self.assertEqual(headers["x-api-key"], "test-key")
        self.assertEqual(headers["anthropic-version"], "2023-06-01")
        self.assertEqual(self.server.requests[0]["system"], "system prompt")
        self.assertEqual(self.server.requests[0]["messages"][0]["content"], "hello")

    async def test_tool_call_and_tool_result_payload(self) -> None:
        self.server.enqueue_json(
            200,
            {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool-1",
                        "name": "read_file",
                        "input": {"path": "main.py"},
                    }
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )
        request = replace(
            _request(),
            messages=(
                Message(
                    role="assistant",
                    tool_calls=(ToolCall(id="tool-1", name="read_file", arguments={}),),
                ),
                Message(role="tool", tool_call_id="tool-1", content="content"),
            ),
        )

        response = await self.provider.complete(request)

        self.assertEqual(response.tool_calls[0].name, "read_file")
        messages = self.server.requests[0]["messages"]
        self.assertEqual(messages[0]["content"][0]["type"], "tool_use")
        self.assertEqual(messages[1]["content"][0]["type"], "tool_result")


if __name__ == "__main__":
    unittest.main()
