"""Resource result types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ResourceResult:
    uri: str
    version: str
    type: str
    title: str
    summary: str
    hash: str
    trust: str
    artifact_refs: tuple[str, ...] = ()
    content: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def payload(self, *, include_content: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "uri": self.uri,
            "version": self.version,
            "type": self.type,
            "title": self.title,
            "summary": self.summary,
            "hash": self.hash,
            "trust": self.trust,
            "artifact_refs": list(self.artifact_refs),
            "metadata": self.metadata,
        }
        if include_content:
            payload["content"] = self.content
        return payload
