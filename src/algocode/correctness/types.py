"""Correctness engine result types."""

from __future__ import annotations

from dataclasses import dataclass, field

from algocode.domain.model import FailureKind


@dataclass(frozen=True, slots=True)
class CaseResult:
    case_id: str
    passed: bool
    duration_seconds: float
    failure_kind: FailureKind | None = None
    message: str = ""
    input: bytes = b""
    actual_output: bytes = b""
    expected_output: bytes | None = None
    oracle_output: bytes | None = None
    actual_stderr: bytes = b""
    actual_exit_code: int | None = None
    expected_exit_code: int | None = None
    oracle_exit_code: int | None = None
    seed: int | None = None
    generator_hash: str | None = None
    input_hash: str | None = None


@dataclass(frozen=True, slots=True)
class CorrectnessResult:
    passed: bool
    status: str
    duration_seconds: float
    cases: tuple[CaseResult, ...] = field(default_factory=tuple)
    failure_kind: FailureKind | None = None
    message: str = ""

    @property
    def passed_cases(self) -> int:
        return sum(1 for case in self.cases if case.passed)

    @property
    def failed_cases(self) -> int:
        return len(self.cases) - self.passed_cases
