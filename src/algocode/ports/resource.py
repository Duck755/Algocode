"""Semantic resource access port."""

from typing import Any, Protocol


class ResourceProvider(Protocol):
    async def resolve(self, uri: str, mode: str = "summary") -> Any: ...
