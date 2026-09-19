from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.domain.model import Task, TaskPhase, new_project_id, new_task_id
from algocode.languages.registry import LanguageRegistry
from algocode.sandbox.runner import SandboxProcessRunner
from algocode.tools import build_default_registry, register_shell_tool
from algocode.tools.builtins.shell import shell_definition
from algocode.tools.types import ToolContext


class ShellToolTests(unittest.IsolatedAsyncioTestCase):
    def test_shell_is_not_registered_by_default(self) -> None:
        names = {definition.name for definition in build_default_registry().definitions()}

        self.assertNotIn("run_shell", names)

    async def test_run_shell_executes_workspace_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            runner = SandboxProcessRunner()
            context = ToolContext(
                task=Task(id=new_task_id(), project_id=new_project_id(), objective="Test"),
                phase=TaskPhase.ANALYZE,
                workspace=workspace,
                language_registry=LanguageRegistry(runner),
            )
            registry = build_default_registry(sandbox=None)
            register_shell_tool(registry)

            result = await registry.execute(
                "run_shell",
                {"command": "echo shell-ok", "timeout_seconds": 10},
                context,
            )

        self.assertEqual(result.status, "success", result.summary)
        self.assertIn("shell-ok", result.structured["stdout"])

    async def test_run_shell_rejects_empty_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = ToolContext(
                task=Task(id=new_task_id(), project_id=new_project_id(), objective="Test"),
                phase=TaskPhase.ANALYZE,
                workspace=Path(directory),
            )
            registry = build_default_registry()
            register_shell_tool(registry)

            result = await registry.execute("run_shell", {"command": "   "}, context)

        self.assertEqual(result.status, "error")
        self.assertIn("empty", result.summary)

    def test_shell_definition_is_execute(self) -> None:
        definition = shell_definition()

        self.assertEqual(definition.name, "run_shell")
        self.assertEqual(definition.effects, "execute")


if __name__ == "__main__":
    unittest.main()

