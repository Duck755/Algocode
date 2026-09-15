from __future__ import annotations

import unittest

from algocode.correctness.protected import find_protected_changes, make_protected_failure
from algocode.domain.model import FailureKind


class ProtectedFilesTests(unittest.TestCase):
    def test_protected_paths_are_detected(self) -> None:
        changes = find_protected_changes(
            ("src/main.py", "tests/test_main.py", ".algocode.yaml"),
            ("tests/", "oracle/", ".algocode.yaml"),
        )

        self.assertEqual(changes, (".algocode.yaml", "tests/test_main.py"))

    def test_protected_failure_has_stable_failure_kind(self) -> None:
        result = make_protected_failure(("tests/test_main.py",))
        self.assertFalse(result.passed)
        self.assertEqual(result.failure_kind, FailureKind.PROTECTED_FILE_CHANGED)


if __name__ == "__main__":
    unittest.main()
