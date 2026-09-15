from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.approval.service import ApprovalService, NonInteractiveApprovalProvider
from algocode.approval.types import ApprovalDecision, ApprovalScope
from algocode.config.model import SandboxConfig
from algocode.domain.model import Task, TaskPhase, new_project_id, new_task_id
from algocode.policy.engine import PolicyEngine
from algocode.policy.types import PolicyEffect, PolicyRule
from algocode.sandbox.local import LocalProcessSandbox
from algocode.storage.sqlite import Database
from algocode.storage.sqlite.approval_store import ApprovalStore
from algocode.tools.registry import ToolRegistry
from algocode.tools.types import ToolContext, ToolDefinition, ToolResult


async def _success(context: ToolContext, arguments: dict[str, object]) -> ToolResult:
    return ToolResult(status="success", summary="written")


class _AllowProvider:
    async def decide(self, request) -> ApprovalDecision:
        return ApprovalDecision(True, ApprovalScope.ONCE, "approved")


class ToolSecurityTests(unittest.IsolatedAsyncioTestCase):
    async def test_ask_requires_approval_and_can_be_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = Database(root / "data")
            database.initialize()
            context = ToolContext(
                task=Task(id=new_task_id(), project_id=new_project_id(), objective="Test"),
                phase=TaskPhase.IMPLEMENT,
                workspace=root,
            )
            definition = ToolDefinition(
                name="write",
                description="write",
                input_schema={"path": {"type": "string", "required": True}},
                effects="write",
            )
            policy = PolicyEngine(
                rules=(PolicyRule("file.write", "*", PolicyEffect.ASK),),
                protected_files=("tests/",),
            )
            sandbox = LocalProcessSandbox(SandboxConfig())
            denied_registry = ToolRegistry(
                policy_engine=policy,
                approval_service=ApprovalService(
                    ApprovalStore(database),
                    NonInteractiveApprovalProvider(),
                ),
                sandbox=sandbox,
            )
            denied_registry.register(definition, _success)

            denied = await denied_registry.execute("write", {"path": "src/main.py"}, context)

            allowed_registry = ToolRegistry(
                policy_engine=policy,
                approval_service=ApprovalService(ApprovalStore(database), _AllowProvider()),
                sandbox=sandbox,
            )
            allowed_registry.register(definition, _success)
            allowed = await allowed_registry.execute("write", {"path": "src/main.py"}, context)

        self.assertEqual(denied.status, "error")
        self.assertEqual(allowed.status, "success")

    async def test_protected_write_is_hard_denied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context = ToolContext(
                task=Task(id=new_task_id(), project_id=new_project_id(), objective="Test"),
                phase=TaskPhase.IMPLEMENT,
                workspace=root,
            )
            registry = ToolRegistry(
                policy_engine=PolicyEngine(
                    rules=(PolicyRule("file.write", "*", PolicyEffect.ALLOW),),
                    protected_files=("tests/",),
                ),
                sandbox=LocalProcessSandbox(SandboxConfig()),
            )
            registry.register(
                ToolDefinition(
                    name="write",
                    description="write",
                    input_schema={"path": {"type": "string", "required": True}},
                    effects="write",
                ),
                _success,
            )
            result = await registry.execute("write", {"path": "tests/test_main.py"}, context)

        self.assertEqual(result.status, "error")
        self.assertIn("policy denied", result.summary)


if __name__ == "__main__":
    unittest.main()
