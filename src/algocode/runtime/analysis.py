"""Runtime-managed analysis coverage and structured report types."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from algocode.languages.discovery import iter_files
from algocode.structured_output import parse_model

MAX_ANALYSIS_FILE_BYTES = 200_000
_BINARY_SUFFIXES = {
    ".a",
    ".bin",
    ".class",
    ".dll",
    ".exe",
    ".gif",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".o",
    ".pdf",
    ".png",
    ".pyc",
    ".so",
    ".webp",
    ".zip",
}


class AnalysisFile(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    path: str
    role: str = "unknown"
    key_symbols: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()


class OptimizationCandidate(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    id: str
    description: str
    expected_effect: str = ""


class AnalysisReport(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    schema_version: int = Field(default=1, ge=1)
    summary: str
    language: str = "unknown"
    project_root: str = "."
    entrypoint_commands: tuple[tuple[str, ...], ...] = ()
    files: tuple[AnalysisFile, ...] = ()
    correctness: dict[str, object] = Field(default_factory=dict)
    benchmark: dict[str, object] = Field(default_factory=dict)
    protected_files: tuple[str, ...] = ()
    optimization_candidates: tuple[OptimizationCandidate, ...] = ()
    unknowns: tuple[str, ...] = ()


class ReadCoverage:
    """Track distinct-turn read coverage for required files."""

    def __init__(self, required_files: tuple[str, ...], required_passes: int = 2) -> None:
        self.required_files = tuple(sorted(required_files))
        self.required_passes = required_passes
        self._turns: dict[str, set[int]] = {path: set() for path in self.required_files}

    def record_read(self, path: str, turn: int) -> None:
        normalized = normalize_relative_path(path)
        if normalized in self._turns:
            self._turns[normalized].add(turn)

    @property
    def complete(self) -> bool:
        if not self.required_files:
            return False
        return all(len(turns) >= self.required_passes for turns in self._turns.values())

    @property
    def completed_count(self) -> int:
        return sum(len(turns) >= self.required_passes for turns in self._turns.values())

    @property
    def total_count(self) -> int:
        return len(self.required_files)

    def missing(self) -> tuple[str, ...]:
        return tuple(
            path for path, turns in self._turns.items() if len(turns) < self.required_passes
        )

    def summary(self) -> str:
        if not self.required_files:
            return "No analyzable files were discovered."
        return (
            f"Read coverage: {self.completed_count}/{self.total_count} files reached "
            f"{self.required_passes} distinct-turn reads. Missing: "
            f"{', '.join(self.missing()) or 'none'}."
        )

    def payload(self) -> dict[str, object]:
        return {
            "required_files": list(self.required_files),
            "required_passes": self.required_passes,
            "completed_files": self.completed_count,
            "total_files": self.total_count,
            "missing_files": list(self.missing()),
            "reads_by_file": {path: sorted(turns) for path, turns in sorted(self._turns.items())},
        }


def discover_required_files(workspace: str | Path) -> tuple[str, ...]:
    root = Path(workspace).resolve()
    files: list[str] = []
    for path in iter_files(root):
        if path.is_symlink() or not path.is_file():
            continue
        if path.name == ".git":
            continue
        if path.suffix.lower() in _BINARY_SUFFIXES:
            continue
        try:
            if path.stat().st_size > MAX_ANALYSIS_FILE_BYTES:
                continue
            sample = path.read_bytes()[:4096]
        except OSError:
            continue
        if b"\x00" in sample:
            continue
        files.append(normalize_relative_path(path.relative_to(root).as_posix()))
    return tuple(sorted(set(files)))


def normalize_relative_path(path: str) -> str:
    normalized = path.replace("\\", "/").lstrip("/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return PurePosixPath(normalized).as_posix()


def parse_analysis_report(text: str) -> AnalysisReport:
    return parse_model(text, AnalysisReport, label="analysis response")


def analysis_summary_prompt(
    coverage: ReadCoverage,
    *,
    previous_error: str | None = None,
) -> str:
    schema = json.dumps(AnalysisReport.model_json_schema(), ensure_ascii=True, indent=2)
    retry = ""
    if previous_error:
        retry = f"\nPrevious response was invalid: {previous_error}\n"
    return (
        "ANALYZE file coverage is complete.\n"
        f"{coverage.summary()}\n"
        "Return only one JSON object matching this schema. Do not call tools. "
        "Do not use Markdown fences. Use only evidence obtained from the reads.\n"
        "For every file, record public APIs, return semantics, ordering and tie-breaking rules, "
        "state transitions, structural/count invariants, error behavior, configuration behavior, "
        "and boundary conditions in constraints. For every optimization candidate, name the "
        "affected public APIs and contract obligations, and state how its effect will be verified. "
        "Put any behavior that could not be verified from the reads in unknowns; do not invent "
        "evidence or silently assume an invariant.\n"
        f"{retry}\nJSON schema:\n{schema}"
    )
