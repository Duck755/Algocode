"""Artifact storage port."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Protocol

from algocode.domain.model import ArtifactRef


class ArtifactStore(Protocol):
    async def put(
        self,
        data: bytes | AsyncIterator[bytes],
        kind: str,
        mime_type: str,
        metadata: Mapping[str, object],
    ) -> ArtifactRef: ...

    def open(self, ref: ArtifactRef) -> AsyncIterator[bytes]: ...

    async def delete(self, ref: ArtifactRef) -> None: ...
