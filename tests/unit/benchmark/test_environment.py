from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.benchmark.environment import compute_environment_hash


class EnvironmentHashTests(unittest.TestCase):
    def test_workspace_dependency_hash_changes_with_lock_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text("[project]\nname = 'a'\n", encoding="utf-8")
            first = compute_environment_hash(root)
            second = compute_environment_hash(root)
            (root / "pyproject.toml").write_text("[project]\nname = 'b'\n", encoding="utf-8")
            changed = compute_environment_hash(root)

        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)


if __name__ == "__main__":
    unittest.main()
