from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.providers.types import (
    Message,
    ModelRef,
    ModelRequest,
    ModelResponse,
    ModelUsage,
    ToolCall,
)
from algocode.runtime.model_log import ModelCallLogger
from algocode.security import SecretRedactor


class ModelCallLoggerTests(unittest.IsolatedAsyncioTestCase):
    async def test_records_full_model_exchange_as_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logger = ModelCallLogger(root, redactor=SecretRedactor(("secret-value",)))
            request = ModelRequest(
                request_id="req_1",
                model=ModelRef(provider_id="mock", model_id="mock-model"),
                system="system instructions",
                messages=(
                    Message(role="user", content="optimize secret-value"),
                    Message(
                        role="assistant",
                        tool_calls=(
                            ToolCall(
                                id="call_1",
                                name="read_file",
                                arguments={"path": "main.py"},
                            ),
                        ),
                    ),
                ),
                tools=({"name": "read_file", "input_schema": {}},),
                metadata={"phase": "implement", "context_hash": "ctx_hash"},
            )
            response = ModelResponse(
                text="I will inspect the file.",
                reasoning="The failure is in the transition table.",
                tool_calls=(
                    ToolCall(
                        id="call_2",
                        name="apply_patch",
                        arguments={"patch": "diff"},
                    ),
                ),
                usage=ModelUsage(input_tokens=10, output_tokens=20, reasoning_tokens=5),
                finish_reason="tool_calls",
            )

            path = await logger.record(
                scope_id="task_1",
                task_id="task_1",
                phase="implement",
                turn=7,
                request=request,
                response=response,
                duration_ms=123,
            )

            text = path.read_text(encoding="utf-8")
            self.assertIn("## System Prompt", text)
            self.assertIn("system instructions", text)
            self.assertIn("## Input Messages", text)
            self.assertIn("read_file", text)
            self.assertIn("## Tool Schemas", text)
            self.assertIn("The failure is in the transition table.", text)
            self.assertIn("apply_patch", text)
            self.assertIn('"input_tokens": 10', text)
            self.assertIn("finish_reason: `tool_calls`", text)
            self.assertNotIn("secret-value", text)
            self.assertTrue((root / "task_1" / "index.md").is_file())


if __name__ == "__main__":
    unittest.main()
