"""Acceptance matrix tests."""

from __future__ import annotations

import unittest
from pathlib import Path

from algocode.acceptance.matrix import load_requirements, validate_requirement_paths


class AcceptanceMatrixTests(unittest.TestCase):
    def test_matrix_is_complete_and_paths_exist(self) -> None:
        root = Path(__file__).resolve().parents[3]
        requirements = load_requirements(root)
        validate_requirement_paths(root, requirements)

        self.assertGreaterEqual(len(requirements), 20)
        self.assertEqual(len({item.id for item in requirements}), len(requirements))
        self.assertTrue(all(item.id.startswith("P0-") for item in requirements))


if __name__ == "__main__":
    unittest.main()
