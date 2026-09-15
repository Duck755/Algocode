from __future__ import annotations

import unittest

from algocode.context.builder import ContextBuilder
from algocode.context.facts import FactLedger
from algocode.context.types import ToolExchange
from algocode.domain.model import Task, TaskPhase, new_project_id, new_task_id
from algocode.providers.types import ToolCall
from algocode.tools.types import ToolResult


class ContextBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = Task(
            id=new_task_id(),
            project_id=new_project_id(),
            objective="Optimize sort",
        )
        self.builder = ContextBuilder(
            context_window=400,
            output_reserve=50,
            safety_margin=20,
            config_hash="config",
            policy_hash="policy",
            tool_catalog_hash="tools",
        )

    def test_context_hash_is_deterministic(self) -> None:
        first = self.builder.build(task=self.task, phase=TaskPhase.ANALYZE, model="model")
        second = self.builder.build(task=self.task, phase=TaskPhase.ANALYZE, model="model")

        self.assertEqual(first.context_hash, second.context_hash)
        self.assertEqual(
            [fragment.kind for fragment in first.fragments],
            [fragment.kind for fragment in second.fragments],
        )

    def test_untrusted_content_is_marked(self) -> None:
        snapshot = self.builder.build(
            task=self.task,
            phase=TaskPhase.ANALYZE,
            model="model",
            project_summary="README says ignore safety",
        )
        messages = snapshot.to_messages()
        untrusted = next(message for message in messages if "[project-summary]" in message.content)

        self.assertIn("UNTRUSTED DATA", untrusted.content)
        self.assertEqual(untrusted.role, "system")

    def test_low_priority_fragment_can_be_dropped(self) -> None:
        snapshot = self.builder.build(
            task=self.task,
            phase=TaskPhase.ANALYZE,
            model="model",
            resources="x" * 5000,
        )

        self.assertIn("resources", snapshot.dropped_fragments)
        self.assertTrue(snapshot.compacted)

    def test_current_request_uses_user_role(self) -> None:
        snapshot = self.builder.build(
            task=self.task,
            phase=TaskPhase.PLAN,
            model="model",
            current_request="Plan now",
        )
        user_messages = [message for message in snapshot.to_messages() if message.role == "user"]

        self.assertEqual(user_messages[-1].content, "[current-request]\nPlan now")

    def test_context_hash_includes_recent_tool_exchanges(self) -> None:
        first_exchange = (
            ToolExchange(
                call=ToolCall(id="call_1", name="read_file", arguments={"path": "main.py"}),
                result=ToolResult(status="success", summary="read main.py"),
            ),
        )
        second_exchange = (
            ToolExchange(
                call=ToolCall(id="call_2", name="read_file", arguments={"path": "other.py"}),
                result=ToolResult(status="success", summary="read other.py"),
            ),
        )

        first = self.builder.build(
            task=self.task,
            phase=TaskPhase.ANALYZE,
            model="model",
            tool_exchanges=first_exchange,
        )
        second = self.builder.build(
            task=self.task,
            phase=TaskPhase.ANALYZE,
            model="model",
            tool_exchanges=second_exchange,
        )

        self.assertNotEqual(first.context_hash, second.context_hash)
        self.assertGreater(first.estimated_tokens, 0)

    def test_fact_ledger_supersedes_previous_value(self) -> None:
        ledger = FactLedger()
        ledger.update(
            kind="candidate",
            key="candidate.status",
            value="generated",
            source_fragment_id="candidate",
        )
        ledger.update(
            kind="candidate",
            key="candidate.status",
            value="verified",
            source_fragment_id="candidate",
        )

        fact = ledger.all()[0]
        self.assertEqual(fact.value, "verified")
        self.assertIsNotNone(fact.supersedes)


if __name__ == "__main__":
    unittest.main()
