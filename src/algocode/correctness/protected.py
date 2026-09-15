"""Protected-file checks for correctness runs."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from algocode.correctness.types import CaseResult, CorrectnessResult
from algocode.domain.model import FailureKind


def find_protected_changes(
    changed_paths: Iterable[str],
    protected_files: Sequence[str],
) -> tuple[str, ...]:
    normalized_protected = tuple(
        pattern.rstrip("/") for pattern in protected_files if pattern.strip()
    )
    changed: list[str] = []
    for path in changed_paths:
        normalized_path = path.replace("\\", "/")
        while normalized_path.startswith("./"):
            normalized_path = normalized_path[2:]
        for pattern in normalized_protected:
            if normalized_path == pattern or normalized_path.startswith(f"{pattern}/"):
                changed.append(normalized_path)
                break
    return tuple(sorted(set(changed)))


def make_protected_failure(changed_paths: tuple[str, ...]) -> CorrectnessResult:

    message = f"protected files changed: {', '.join(changed_paths)}"
    case = CaseResult(
        case_id="protected-files",
        passed=False,
        duration_seconds=0.0,
        failure_kind=FailureKind.PROTECTED_FILE_CHANGED,
        message=message,
    )
    return CorrectnessResult(
        passed=False,
        status="failed",
        duration_seconds=0.0,
        cases=(case,),
        failure_kind=FailureKind.PROTECTED_FILE_CHANGED,
        message=message,
    )
