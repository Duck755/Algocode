"""Policy evaluation port."""

from typing import Any, Protocol


class PolicyEngine(Protocol):
    async def evaluate(self, request: object) -> Any: ...
