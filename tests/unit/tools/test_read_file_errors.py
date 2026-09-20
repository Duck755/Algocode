from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.domain.model import Task, TaskPhase, new_project_id, new_task_id
from algocode.tools import build_default_registry
from algocode.tools.types import ToolContext


class ReadFileErrorTests(unittest.IsolatedAsyncioTestCase):
    async def _read(self, workspace: Path, path: str) -> str:
        context = ToolContext(
            task=Task(id=new_task_id(), project_id=new_project_id(), objective="Test"),
            phase=TaskPhase.IMPLEMENT,
            workspace=workspace,
        )

        result = await build_default_registry().execute("read_file", {"path": path}, context)

        self.assertEqual(result.status, "error")
        return result.summary

    async def test_a_directory_explains_itself(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / ".algocode").mkdir()
            (workspace / ".algocode" / "config.yaml").write_text("version: 1\n", encoding="utf-8")

            summary = await self._read(workspace, ".algocode")

        self.assertIn("is a directory", summary)
        self.assertIn("config.yaml", summary)
        self.assertIn("list_files", summary)

    async def test_a_missing_file_lists_its_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "src").mkdir()
            (workspace / "src" / "solution.py").write_text("print(1)\n", encoding="utf-8")

            summary = await self._read(workspace, "src/main.py")

        self.assertIn("file not found: src/main.py", summary)
        self.assertIn("solution.py", summary)

    async def test_an_unknown_path_points_at_listing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)

            summary = await self._read(workspace, "nowhere/deep/file.py")

        self.assertIn("file not found", summary)
        self.assertIn("list_files", summary)


if __name__ == "__main__":
    unittest.main()
