from __future__ import annotations

import unittest

from algocode.policy.engine import PolicyEngine
from algocode.policy.types import PolicyEffect, PolicyLayer, PolicyRequest, PolicyRule


class PolicyEngineTests(unittest.TestCase):
    def test_protected_write_is_hard_denied(self) -> None:
        engine = PolicyEngine(
            rules=(PolicyRule("file.write", "*", PolicyEffect.ALLOW),),
            protected_files=("tests/",),
        )

        decision = engine.evaluate(PolicyRequest("file.write", "tests/test_main.py"))

        self.assertEqual(decision.effect, PolicyEffect.DENY)
        self.assertEqual(decision.layer, PolicyLayer.HARD)

    def test_layer_precedence_and_last_match_wins(self) -> None:
        engine = PolicyEngine(
            rules=(
                PolicyRule("file.write", "*", PolicyEffect.ALLOW, PolicyLayer.PROJECT),
                PolicyRule("file.write", "src/*", PolicyEffect.DENY, PolicyLayer.PROJECT),
                PolicyRule("file.write", "src/main.py", PolicyEffect.ALLOW, PolicyLayer.USER),
            )
        )

        decision = engine.evaluate(PolicyRequest("file.write", "src/main.py"))

        self.assertEqual(decision.effect, PolicyEffect.ALLOW)
        self.assertEqual(decision.layer, PolicyLayer.USER)

    def test_default_effect_is_used_without_match(self) -> None:
        engine = PolicyEngine(default_effect=PolicyEffect.DENY)
        decision = engine.evaluate(PolicyRequest("custom.action", "x"))

        self.assertEqual(decision.effect, PolicyEffect.DENY)
        self.assertIsNone(decision.layer)

    def test_policy_hash_is_stable(self) -> None:
        rule = PolicyRule("file.write", "src/*", PolicyEffect.ASK)
        first = PolicyEngine(rules=(rule,))
        second = PolicyEngine(rules=(rule,))

        self.assertEqual(first.hash(), second.hash())


if __name__ == "__main__":
    unittest.main()
