"""Immutable domain value objects."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    uri: str
    sha256: str


@dataclass(frozen=True, slots=True)
class GitRevision:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("Git revision must not be empty")
