"""Deterministic fact ledger retained across context compaction."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from algocode.context.types import ContextFact


class FactLedger:
    def __init__(self) -> None:
        self._facts: dict[str, ContextFact] = {}

    def update(
        self,
        *,
        kind: str,
        key: str,
        value: str,
        source_fragment_id: str,
        evidence_refs: tuple[str, ...] = (),
    ) -> None:
        previous = self._facts.get(key)
        self._facts[key] = ContextFact(
            id=f"fact_{uuid4().hex}",
            kind=kind,
            key=key,
            value=value,
            source_fragment_id=source_fragment_id,
            evidence_refs=evidence_refs,
            created_at=datetime.now(UTC).isoformat(),
            supersedes=previous.id if previous is not None else None,
        )

    def all(self) -> tuple[ContextFact, ...]:
        return tuple(self._facts.values())
