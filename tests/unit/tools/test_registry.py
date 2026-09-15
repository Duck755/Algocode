from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.domain.model import Task, TaskPhase, new_project_id, new_task_id
from algocode.tools import build_default_registry
from algocode.tools.types import ToolContext


class ToolRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_tools_return_workspace_facts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "main.py").write_text("def solve():\n    return 42\n", encoding="utf-8")
            context = ToolContext(
                task=Task(id=new_task_id(), project_id=new_project_id(), objective="Test"),
                phase=TaskPhase.ANALYZE,
                workspace=workspace,
            )
            registry = build_default_registry()

            listed = await registry.execute("list_files", {"pattern": "*"}, context)
            read = await registry.execute("read_file", {"path": "main.py"}, context)
            searched = await registry.execute("search_code", {"query": "solve"}, context)

        self.assertEqual(listed.status, "success")
        self.assertIn("main.py", listed.structured["paths"])
        self.assertIn("return 42", read.structured["content"])
        self.assertEqual(searched.structured["matches"][0]["path"], "main.py")

    async def test_read_file_rejects_workspace_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            context = ToolContext(
                task=Task(id=new_task_id(), project_id=new_project_id(), objective="Test"),
                phase=TaskPhase.ANALYZE,
                workspace=workspace,
            )
            result = await build_default_registry().execute(
                "read_file",
                {"path": "../outside.txt"},
                context,
            )

        self.assertEqual(result.status, "error")
        self.assertIn("escapes", result.summary)

    async def test_submit_phase_result_validates_phase(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = ToolContext(
                task=Task(id=new_task_id(), project_id=new_project_id(), objective="Test"),
                phase=TaskPhase.PLAN,
                workspace=Path(directory),
            )
            result = await build_default_registry().execute(
                "submit_phase_result",
                {
                    "phase": "implement",
                    "status": "completed",
                    "summary": "done",
                },
                context,
            )

        self.assertEqual(result.status, "error")
        self.assertIn("does not match", result.summary)


if __name__ == "__main__":
    unittest.main()
