"""Deterministic policy evaluation."""

from __future__ import annotations

import fnmatch
import hashlib
import json
from collections.abc import Sequence

from algocode.policy.types import (
    PolicyDecision,
    PolicyEffect,
    PolicyLayer,
    PolicyRequest,
    PolicyRule,
)

_LAYER_ORDER = (
    PolicyLayer.HARD,
    PolicyLayer.MANAGED,
    PolicyLayer.USER,
    PolicyLayer.PROJECT,
    PolicyLayer.DEFAULT,
)

_HARD_RULES = (
    PolicyRule("secret.read", "*", PolicyEffect.DENY, PolicyLayer.HARD),
    PolicyRule("file.write.outside_workspace", "*", PolicyEffect.DENY, PolicyLayer.HARD),
    PolicyRule("benchmark.input.write", "*", PolicyEffect.DENY, PolicyLayer.HARD),
)

_DEFAULT_RULES = (
    PolicyRule("file.read", "*", PolicyEffect.ALLOW, PolicyLayer.DEFAULT),
    PolicyRule("file.write", "*", PolicyEffect.ALLOW, PolicyLayer.DEFAULT),
    PolicyRule("process.execute", "*", PolicyEffect.ALLOW, PolicyLayer.DEFAULT),
    PolicyRule("control", "*", PolicyEffect.ALLOW, PolicyLayer.DEFAULT),
    PolicyRule("network.connect", "*", PolicyEffect.DENY, PolicyLayer.DEFAULT),
)


class PolicyEngine:
    """Evaluate layered rules using Last Match Wins inside each layer."""

    def __init__(
        self,
        *,
        rules: Sequence[PolicyRule] = (),
        default_effect: PolicyEffect = PolicyEffect.ASK,
        protected_files: Sequence[str] = (),
    ) -> None:
        self._rules = (*_HARD_RULES, *rules, *_DEFAULT_RULES)
        self.default_effect = default_effect
        self.protected_files = tuple(protected_files)

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        if self._is_protected_write(request):
            return PolicyDecision(
                effect=PolicyEffect.DENY,
                reason="protected files cannot be modified",
                layer=PolicyLayer.HARD,
            )
        for layer in _LAYER_ORDER:
            matches = [
                rule for rule in self._rules if rule.layer is layer and _matches(rule, request)
            ]
            if matches:
                rule = matches[-1]
                return PolicyDecision(
                    effect=rule.effect,
                    reason=f"matched {layer.value} rule {rule.action}:{rule.resource}",
                    layer=layer,
                    matched_rule=rule,
                )
        return PolicyDecision(
            effect=self.default_effect,
            reason="no policy rule matched",
        )

    def hash(self) -> str:
        payload = [
            {
                "action": rule.action,
                "resource": rule.resource,
                "effect": rule.effect.value,
                "layer": rule.layer.value,
            }
            for rule in self._rules
        ]
        canonical = json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _is_protected_write(self, request: PolicyRequest) -> bool:
        if request.action != "file.write":
            return False
        resource = request.resource.replace("\\", "/").lstrip("./")
        return any(
            resource == pattern.rstrip("/") or resource.startswith(f"{pattern.rstrip('/')}/")
            for pattern in self.protected_files
        )


def _matches(rule: PolicyRule, request: PolicyRequest) -> bool:
    return fnmatch.fnmatchcase(request.action, rule.action) and fnmatch.fnmatchcase(
        request.resource,
        rule.resource,
    )
