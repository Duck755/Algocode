from __future__ import annotations

import unittest

from algocode.reproducibility import component_seeds, derive_seed


class ReproducibilityTests(unittest.TestCase):
    def test_derive_seed_is_deterministic_and_component_sensitive(self) -> None:
        first = derive_seed(42, "eval", "suite-a")
        second = derive_seed(42, "eval", "suite-a")
        different = derive_seed(42, "eval", "suite-b")

        self.assertEqual(first, second)
        self.assertNotEqual(first, different)
        self.assertGreaterEqual(first, 0)
        self.assertLessEqual(first, 0x7FFFFFFF)

    def test_component_seeds_are_independent(self) -> None:
        seeds = component_seeds(7, (("eval", "a"), ("eval", "b"), ("eval", "a")))
        self.assertEqual(seeds[0], seeds[2])
        self.assertNotEqual(seeds[0], seeds[1])


if __name__ == "__main__":
    unittest.main()
