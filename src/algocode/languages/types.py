"""Shared language adapter result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from algocode.domain.model import Language


def resolve_source_root(workspace: Path, source_root: str) -> Path:
    resolved_workspace = workspace.resolve()
    resolved_source = (resolved_workspace / source_root).resolve()
    if not resolved_source.is_relative_to(resolved_workspace):
        raise ValueError("source_root must stay inside the workspace")
    return resolved_source


@dataclass(frozen=True, slots=True)
class Diagnostic:
    severity: str
    message: str
    file: str | None = None
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True, slots=True)
class ProjectInfo:
    root: Path
    languages: tuple[Language, ...]
    build_system: str | None = None

    @property
    def primary_language(self) -> Language | None:
        if len(self.languages) == 1:
            return self.languages[0]
        if Language.CPP in self.languages:
            return Language.CPP
        if Language.PYTHON in self.languages:
            return Language.PYTHON
        return None


@dataclass(frozen=True, slots=True)
class PrepareResult:
    workspace: Path
    prepared: bool = True
    message: str = ""


@dataclass(frozen=True, slots=True)
class BuildProfile:
    commands: tuple[tuple[str, ...], ...] = ()
    source_root: str = "."
    timeout_seconds: int = 120


@dataclass(frozen=True, slots=True)
class BuildResult:
    language: Language
    commands: tuple[tuple[str, ...], ...]
    exit_code: int
    duration_seconds: float
    stdout: bytes = b""
    stderr: bytes = b""
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)
    executable: Path | None = None
    run_command: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0

    @property
    def output(self) -> bytes:
        return self.stdout + self.stderr
