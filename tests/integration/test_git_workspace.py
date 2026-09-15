from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.workspace import GitRepository, GitWorkspaceManager
from tests.support.git import git_output, init_git_repository


class GitWorkspaceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.repository_root = init_git_repository(
            self.root / "project",
            {
                "src/main.cpp": "int main() { return 0; }\n",
                "README.md": "example\n",
            },
        )
        self.data_dir = self.root / "data"
        self.repository = await GitRepository.discover(self.repository_root)
        self.manager = GitWorkspaceManager(self.repository, self.data_dir)

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_dirty_repository_is_reconstructed_in_worktree(self) -> None:
        (self.repository_root / "README.md").write_text("changed\n", encoding="utf-8")
        (self.repository_root / "new.txt").write_text("untracked\n", encoding="utf-8")
        revision = git_output(self.repository_root, "rev-parse", "HEAD")

        workspace = await self.manager.prepare_baseline("task_1", revision)

        self.assertEqual((workspace.path / "README.md").read_text(encoding="utf-8"), "changed\n")
        self.assertEqual((workspace.path / "new.txt").read_text(encoding="utf-8"), "untracked\n")
        self.assertNotEqual(workspace.base_snapshot_hash, revision)

    async def test_candidate_apply_and_rollback(self) -> None:
        revision = git_output(self.repository_root, "rev-parse", "HEAD")
        workspace = await self.manager.create_candidate("task_1", revision)
        source = workspace.path / "src/main.cpp"
        source.write_text("int main() { return 7; }\n", encoding="utf-8")
        (workspace.path / "candidate.txt").write_text("candidate\n", encoding="utf-8")

        patch_hash = await self.manager.freeze(workspace)
        self.assertEqual(len(patch_hash), 64)
        self.assertIn("candidate.txt", await self.manager.diff(workspace))

        result = await self.manager.apply(workspace)
        self.assertTrue(result.applied)
        self.assertIn("return 7", (self.repository_root / "src/main.cpp").read_text("utf-8"))
        self.assertEqual(
            (self.repository_root / "candidate.txt").read_text("utf-8"),
            "candidate\n",
        )

        await self.manager.rollback(workspace)
        self.assertIn("return 0", (self.repository_root / "src/main.cpp").read_text("utf-8"))
        self.assertFalse((self.repository_root / "candidate.txt").exists())


if __name__ == "__main__":
    unittest.main()
