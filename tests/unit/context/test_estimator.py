from __future__ import annotations

import unittest

from algocode.context.estimator import estimate_tokens, truncate_to_tokens


class EstimatorTests(unittest.TestCase):
    def test_estimate_tokens_is_positive_and_deterministic(self) -> None:
        first = estimate_tokens("def solve():\n    return 42")
        second = estimate_tokens("def solve():\n    return 42")
        self.assertEqual(first, second)
        self.assertGreater(first, 0)

    def test_truncate_to_tokens_preserves_short_text(self) -> None:
        text = "short text"
        self.assertEqual(truncate_to_tokens(text, 100), text)

    def test_truncate_to_tokens_respects_zero_budget(self) -> None:
        self.assertEqual(truncate_to_tokens("anything", 0), "")


if __name__ == "__main__":
    unittest.main()
