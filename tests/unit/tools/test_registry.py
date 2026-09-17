from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.domain.model import Task, TaskPhase, new_project_id, new_task_id
from algocode.tools import build_default_registry
from algocode.tools.types import ToolContext
from tests.support.git import init_git_repository


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
            required = await registry.execute("read_required_files", {}, context)
            searched = await registry.execute("search_code", {"query": "solve"}, context)
            file_size = (workspace / "main.py").stat().st_size

        self.assertEqual(listed.status, "success")
        self.assertIn("main.py", listed.structured["paths"])
        self.assertIn("return 42", read.structured["content"])
        self.assertEqual(searched.structured["matches"][0]["path"], "main.py")
        self.assertEqual(len(read.structured["sha256"]), 64)
        self.assertEqual(required.structured["files"][0]["path"], "main.py")
        self.assertEqual(read.structured["size"], file_size)

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

    async def test_continue_phase_status_is_normalized_to_completed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = ToolContext(
                task=Task(id=new_task_id(), project_id=new_project_id(), objective="Test"),
                phase=TaskPhase.PLAN,
                workspace=Path(directory),
            )
            result = await build_default_registry().execute(
                "submit_phase_result",
                {"phase": "plan", "status": "continue", "summary": "planned"},
                context,
            )

        self.assertEqual(result.status, "success")
        self.assertEqual(result.structured["status"], "completed")

    async def test_long_running_tools_have_adequate_wrapper_timeout(self) -> None:
        definitions = {
            definition.name: definition for definition in build_default_registry().definitions()
        }

        self.assertGreaterEqual(definitions["run_correctness"].timeout_seconds, 300)
        self.assertGreaterEqual(definitions["run_benchmark"].timeout_seconds, 900)

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

    async def test_plan_tool_validates_nested_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = ToolContext(
                task=Task(id=new_task_id(), project_id=new_project_id(), objective="Test"),
                phase=TaskPhase.PLAN,
                workspace=Path(directory),
            )
            result = await build_default_registry().execute(
                "submit_optimization_plan",
                {
                    "summary": "Optimize",
                    "strategy": "Patch",
                    "steps": [{"id": "s1"}],
                },
                context,
            )

        self.assertEqual(result.status, "error")
        self.assertIn("steps.0", result.summary)

    async def test_write_and_edit_file_require_candidate_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = init_git_repository(
                root / "repo",
                {"main.py": "def solve():\n    return 42\n"},
            )
            context = ToolContext(
                task=Task(id=new_task_id(), project_id=new_project_id(), objective="Test"),
                phase=TaskPhase.IMPLEMENT,
                workspace=workspace,
                candidate_id="cand_test",
            )
            registry = build_default_registry()
            original = await registry.execute("read_file", {"path": "main.py"}, context)

            written = await registry.execute(
                "write_file",
                {
                    "path": "main.py",
                    "content": "def solve():\r\n    return 84\r\n",
                    "expected_sha256": original.structured["sha256"],
                },
                context,
            )
            edited_read = await registry.execute("read_file", {"path": "main.py"}, context)
            edited = await registry.execute(
                "edit_file",
                {
                    "path": "main.py",
                    "old_text": "return 84",
                    "new_text": "return 126",
                    "expected_sha256": edited_read.structured["sha256"],
                },
                context,
            )
            protected = await registry.execute(
                "write_file",
                {
                    "path": "oracle/check.py",
                    "content": "print('bad')\n",
                },
                ToolContext(
                    task=context.task,
                    phase=TaskPhase.IMPLEMENT,
                    workspace=workspace,
                    candidate_id="cand_test",
                    protected_files=("oracle/",),
                ),
            )
            edited_content = (workspace / "main.py").read_text(encoding="utf-8")
            edited_bytes = (workspace / "main.py").read_bytes()

        self.assertEqual(written.status, "success", written.summary)
        self.assertEqual(edited.status, "success", edited.summary)
        self.assertIn("return 126", edited_content)
        self.assertNotIn(b"\r", edited_bytes)
        self.assertEqual(protected.status, "error")
        self.assertIn("protected", protected.summary)


if __name__ == "__main__":
    unittest.main()
