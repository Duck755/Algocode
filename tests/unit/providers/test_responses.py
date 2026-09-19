from __future__ import annotations

import unittest

from algocode.providers.responses import ResponsesProvider
from algocode.providers.types import Message, ModelRef, ModelRequest, ToolCall
from tests.support.mock_openai import MockOpenAIServer


def _request() -> ModelRequest:
    return ModelRequest(
        request_id="req",
        model=ModelRef(provider_id="responses", model_id="gpt-test"),
        system="system prompt",
        messages=(Message(role="user", content="hello"),),
        tools=(
            {
                "name": "list_files",
                "description": "List files.",
                "input_schema": {"pattern": {"type": "string"}},
            },
        ),
        timeout_seconds=5,
    )


class ResponsesProviderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.server = MockOpenAIServer()
        self.server.__enter__()
        self.provider = ResponsesProvider(
            provider_id="responses",
            base_url=self.server.base_url,
            api_key="test-key",
            model_id="gpt-test",
        )

    def tearDown(self) -> None:
        self.server.__exit__(None, None, None)

    async def test_complete_parses_responses_output_and_usage(self) -> None:
        self.server.enqueue_json(
            200,
            {
                "id": "resp-1",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "hello"}],
                    },
                    {
                        "type": "function_call",
                        "call_id": "call-1",
                        "name": "list_files",
                        "arguments": '{"pattern": "*"}',
                    },
                ],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

        response = await self.provider.complete(_request())

        self.assertEqual(response.text, "hello")
        self.assertEqual(response.tool_calls[0].name, "list_files")
        self.assertEqual(response.tool_calls[0].arguments, {"pattern": "*"})
        self.assertEqual(response.usage.input_tokens, 10)
        self.assertEqual(response.usage.output_tokens, 5)
        self.assertEqual(self.server.requests[0]["model"], "gpt-test")
        self.assertEqual(self.server.requests[0]["tools"][0]["name"], "list_files")

    async def test_tool_output_maps_to_function_call_output(self) -> None:
        self.server.enqueue_json(
            200,
            {
                "id": "resp-2",
                "status": "completed",
                "output": [],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )
        request = ModelRequest(
            request_id="req",
            model=ModelRef(provider_id="responses", model_id="gpt-test"),
            system="",
            messages=(
                Message(
                    role="assistant",
                    tool_calls=(ToolCall(id="call-1", name="list_files", arguments={}),),
                ),
                Message(role="tool", tool_call_id="call-1", content="result"),
            ),
            timeout_seconds=5,
        )

        await self.provider.complete(request)

        input_items = self.server.requests[0]["input"]
        self.assertEqual(input_items[0]["type"], "function_call")
        self.assertEqual(input_items[1]["type"], "function_call_output")
        self.assertEqual(input_items[1]["output"], "result")


if __name__ == "__main__":
    unittest.main()
