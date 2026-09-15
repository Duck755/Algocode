"""Model provider port."""

from collections.abc import AsyncIterator
from typing import Protocol

from algocode.providers.types import ModelEvent, ModelRequest, ModelResponse


class ProviderAdapter(Protocol):
    async def complete(self, request: ModelRequest) -> ModelResponse: ...

    def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]: ...
