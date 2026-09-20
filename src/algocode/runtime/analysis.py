"""Runtime-managed analysis coverage and structured report types."""

from __future__ import annotations

import json
import shlex
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from algocode.languages.discovery import iter_files
from algocode.structured_output import parse_model

MAX_ANALYSIS_FILE_BYTES = 200_000
MIN_ALGORITHM_CANDIDATES = 3
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


class ProblemStructure(BaseModel):
    """Distributional and algebraic facts that decide which algorithm is viable."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    input_model: str = ""
    data_distribution: str = ""
    operation_algebra: str = ""
    query_update_mix: str = ""
    monotonicity: str = ""
    constraints: tuple[str, ...] = ()


class ComplexityBaseline(BaseModel):
    """Where the current implementation sits relative to the best known approach."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    current: str = ""
    known_best: str = ""
    gap: str = ""
    reasoning: str = ""


class AlgorithmCandidate(BaseModel):
    """One algorithmic approach that could replace the current implementation."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    name: str = ""
    paradigm: str = ""
    complexity: str = ""
    applicability: str = ""
    expected_gain: str = ""


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
    profile: dict[str, object] = Field(default_factory=dict)
    protected_files: tuple[str, ...] = ()
    optimization_candidates: tuple[OptimizationCandidate, ...] = ()
    problem_structure: ProblemStructure | None = None
    complexity_baseline: ComplexityBaseline | None = None
    algorithm_candidates: tuple[AlgorithmCandidate, ...] = ()
    unknowns: tuple[str, ...] = ()

    @field_validator("entrypoint_commands", mode="before")
    @classmethod
    def _normalize_entrypoint_commands(cls, value):
        if value is None:
            return ()
        if isinstance(value, str):
            value = (value,)
        if not isinstance(value, (list, tuple)):
            return value
        commands: list[tuple[str, ...]] = []
        for command in value:
            if isinstance(command, str):
                parts = shlex.split(command, posix=False)
                commands.append(
                    tuple(part.strip("\"'") for part in parts if part.strip("\"'"))
                )
            elif isinstance(command, (list, tuple)):
                commands.append(tuple(str(part) for part in command))
            else:
                commands.append((str(command),))
        return tuple(commands)


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


def validate_analysis_depth(report: AnalysisReport) -> list[str]:
    """Return the missing pieces of algorithmic analysis, if any.

    The report must describe the problem structure, place the current
    implementation against the best known complexity, and name several
    algorithmic approaches. Without them the planner can only micro-optimize
    the existing hot path, which never changes asymptotic behaviour.
    """
    issues: list[str] = []
    structure = report.problem_structure
    if structure is None:
        issues.append("problemStructure is missing")
    else:
        for field in (
            "input_model",
            "data_distribution",
            "operation_algebra",
            "query_update_mix",
            "monotonicity",
        ):
            if not getattr(structure, field).strip():
                issues.append(f"problemStructure.{to_camel(field)} is empty")
    baseline = report.complexity_baseline
    if baseline is None:
        issues.append("complexityBaseline is missing")
    else:
        for field in ("current", "known_best", "gap", "reasoning"):
            if not getattr(baseline, field).strip():
                issues.append(f"complexityBaseline.{to_camel(field)} is empty")
    if len(report.algorithm_candidates) < MIN_ALGORITHM_CANDIDATES:
        issues.append(
            f"algorithmCandidates needs at least {MIN_ALGORITHM_CANDIDATES} entries"
        )
    for index, candidate in enumerate(report.algorithm_candidates):
        for field in ("name", "paradigm", "complexity", "applicability"):
            if not getattr(candidate, field).strip():
                issues.append(f"algorithmCandidates[{index}].{field} is empty")
    return issues


def parse_analysis_report(text: str) -> AnalysisReport:
    """Parse a model analysis report and reject shallow ones.

    A report without structure and complexity evidence cannot justify an
    algorithmic change, so it is reported back to the model as an error and
    the phase retries.
    """
    report = parse_model(text, AnalysisReport, label="analysis response")
    issues = validate_analysis_depth(report)
    if issues:
        raise ValueError(
            "analysis report lacks algorithmic depth: "
            + "; ".join(issues)
            + ". Describe the problem structure, compare the current complexity with the"
            " best known approach, and list at least three candidate algorithms."
        )
    return report


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
        "entrypointCommands must contain command argument arrays, for example "
        '[["python", "test.py"]]. Do not put a full command in one string.\n'
        "Do not use Markdown fences. Use only evidence obtained from the reads.\n"
        "For every file, record public APIs, return semantics, ordering and tie-breaking rules, "
        "state transitions, structural/count invariants, error behavior, configuration behavior, "
        "and boundary conditions in constraints. For every optimization candidate, name the "
        "affected public APIs and contract obligations, and state how its effect will be verified. "
        "Put any behavior that could not be verified from the reads in unknowns; do not invent "
        "evidence or silently assume an invariant.\n"
        "Fill problemStructure with what the input actually looks like: how input size is "
        "determined, how values are distributed, which operations are associative, commutative "
        "or idempotent, the query/update ratio, any monotonicity, and the binding "
        "constraints. Fill complexityBaseline with the complexity of the current "
        "implementation, the best known complexity for this problem, the gap between them, "
        "and the reasoning. "
        f"List at least {MIN_ALGORITHM_CANDIDATES} algorithmCandidates; each must name a "
        "concrete algorithm or data structure, its paradigm, its complexity, when it applies, "
        "and the expected gain. Include the alternatives you rejected and say why. If the "
        "current algorithm is already optimal, still list the alternatives you evaluated. "
        "The report is rejected when any of these fields is empty.\n"
        "Leave profile as an empty object; the runtime populates it with verified "
        "profiler hotspots.\n"
        f"{retry}\nJSON schema:\n{schema}"
    )
