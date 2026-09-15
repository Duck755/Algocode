"""Language-independent correctness execution engine."""

from __future__ import annotations

import hashlib
import json
import tempfile
import time
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

from algocode.correctness.spec import CorrectnessSpec
from algocode.correctness.types import CaseResult, CorrectnessResult
from algocode.domain.model import ComparisonMode, CorrectnessMode, CorrectnessStatus, FailureKind
from algocode.sandbox.runner import SandboxProcessRunner

_SANDBOX_RUNNER: ContextVar[SandboxProcessRunner | None] = ContextVar(
    "correctness_sandbox_runner",
    default=None,
)


@dataclass(frozen=True, slots=True)
class _ProcessResult:
    exit_code: int
    stdout: bytes
    stderr: bytes
    duration_seconds: float
    timed_out: bool = False
    start_failed: bool = False


async def run_process_correctness(
    workspace: Path,
    spec: CorrectnessSpec,
    sandbox_runner: SandboxProcessRunner | None = None,
) -> CorrectnessResult:
    token = _SANDBOX_RUNNER.set(sandbox_runner)
    try:
        return await _run_process_correctness(workspace, spec)
    finally:
        _SANDBOX_RUNNER.reset(token)


async def _run_process_correctness(
    workspace: Path,
    spec: CorrectnessSpec,
) -> CorrectnessResult:
    """Execute a correctness specification against one prepared workspace."""

    started = time.perf_counter()
    cases = _build_cases(spec)
    results: list[CaseResult] = []
    for case_id, case_input, expected_output, expected_exit_code, args, timeout, seed in cases:
        result = await _run_one_case(
            workspace,
            spec,
            case_id=case_id,
            input_bytes=case_input,
            expected_output=expected_output,
            expected_exit_code=expected_exit_code,
            args=args,
            timeout_seconds=timeout,
            seed=seed,
        )
        results.append(result)
        if not result.passed:
            break

    failed = next((result for result in results if not result.passed), None)
    if failed is None and not results:
        failed = CaseResult(
            case_id="none",
            passed=False,
            failure_kind=FailureKind.INCONCLUSIVE,
            message="correctness spec produced no executable cases",
            duration_seconds=0.0,
        )
    passed = failed is None
    return CorrectnessResult(
        passed=passed,
        status=(CorrectnessStatus.PASSED.value if passed else CorrectnessStatus.FAILED.value),
        duration_seconds=time.perf_counter() - started,
        cases=tuple(results),
        failure_kind=None if failed is None else failed.failure_kind,
        message="" if failed is None else failed.message,
    )


def _build_cases(
    spec: CorrectnessSpec,
) -> tuple[
    tuple[
        str,
        bytes,
        bytes | None,
        int,
        tuple[str, ...],
        int,
        int | None,
    ],
    ...,
]:
    if spec.mode is CorrectnessMode.STRESS:
        return tuple(
            (
                f"stress-{index + 1}",
                b"",
                None,
                0,
                (),
                spec.timeout_seconds,
                spec.seed + index,
            )
            for index in range(spec.iterations)
        )
    if spec.cases:
        return tuple(
            (
                case.id,
                case.input.encode(),
                (case.expected_output.encode() if case.expected_output is not None else None),
                case.expected_exit_code,
                case.args,
                case.timeout_seconds or spec.timeout_seconds,
                None,
            )
            for case in spec.cases
        )
    return (("oracle-1", b"", None, 0, (), spec.timeout_seconds, None),)


async def _run_one_case(
    workspace: Path,
    spec: CorrectnessSpec,
    *,
    case_id: str,
    input_bytes: bytes,
    expected_output: bytes | None,
    expected_exit_code: int,
    args: tuple[str, ...],
    timeout_seconds: int,
    seed: int | None,
) -> CaseResult:
    started = time.perf_counter()
    generator_hash: str | None = None
    if spec.mode is CorrectnessMode.STRESS and seed is not None:
        generator = await _run_process(
            _expand_command(spec.generator_command, workspace),
            workspace=workspace,
            input_bytes=b"",
            timeout_seconds=timeout_seconds,
            extra_env={"ALGOCODE_SEED": str(seed), "ALGOCODE_CASE_ID": case_id},
        )
        generator_hash = _hash_payload(
            {
                "command": list(spec.generator_command),
                "seed": seed,
                "iteration": case_id,
            }
        )
        if not generator.exit_code == 0:
            return CaseResult(
                case_id=case_id,
                passed=False,
                duration_seconds=time.perf_counter() - started,
                failure_kind=FailureKind.GENERATOR_FAILED,
                message="stress generator failed",
                actual_stderr=generator.stderr,
                actual_exit_code=generator.exit_code,
                seed=seed,
                generator_hash=generator_hash,
            )
        input_bytes = generator.stdout

    candidate_command = _expand_command(spec.run_command, workspace) + args
    candidate = await _run_process(
        candidate_command,
        workspace=workspace,
        input_bytes=input_bytes,
        timeout_seconds=timeout_seconds,
        extra_env={"ALGOCODE_CASE_ID": case_id, "ALGOCODE_SEED": str(seed or 0)},
    )
    if candidate.start_failed:
        return _failed_case(
            case_id,
            input_bytes,
            candidate,
            FailureKind.PROCESS_CRASH,
            "candidate process could not be started",
            seed,
            generator_hash,
            expected_exit_code,
        )
    if candidate.timed_out:
        return _failed_case(
            case_id,
            input_bytes,
            candidate,
            FailureKind.TIMEOUT,
            "candidate process timed out",
            seed,
            generator_hash,
            expected_exit_code,
        )
    if candidate.exit_code != expected_exit_code:
        return _failed_case(
            case_id,
            input_bytes,
            candidate,
            FailureKind.PROCESS_CRASH,
            f"candidate exited with {candidate.exit_code}, expected {expected_exit_code}",
            seed,
            generator_hash,
            expected_exit_code,
        )

    oracle: _ProcessResult | None = None
    if expected_output is None:
        oracle = await _run_process(
            _expand_command(spec.oracle_command, workspace),
            workspace=workspace,
            input_bytes=input_bytes,
            timeout_seconds=timeout_seconds,
            extra_env={"ALGOCODE_CASE_ID": case_id, "ALGOCODE_SEED": str(seed or 0)},
        )
        if oracle.start_failed or oracle.timed_out or oracle.exit_code != 0:
            return CaseResult(
                case_id=case_id,
                passed=False,
                duration_seconds=time.perf_counter() - started,
                failure_kind=FailureKind.ORACLE_FAILED,
                message="oracle failed to produce a valid result",
                input=input_bytes,
                actual_output=candidate.stdout,
                actual_stderr=candidate.stderr,
                actual_exit_code=candidate.exit_code,
                expected_exit_code=expected_exit_code,
                oracle_output=oracle.stdout,
                oracle_exit_code=oracle.exit_code,
                seed=seed,
                generator_hash=generator_hash,
                input_hash=_hash_bytes(input_bytes),
            )
        expected_output = oracle.stdout

    if spec.require_determinism:
        repeated = await _run_process(
            candidate_command,
            workspace=workspace,
            input_bytes=input_bytes,
            timeout_seconds=timeout_seconds,
            extra_env={"ALGOCODE_CASE_ID": case_id, "ALGOCODE_SEED": str(seed or 0)},
        )
        if repeated.exit_code != candidate.exit_code or repeated.stdout != candidate.stdout:
            return CaseResult(
                case_id=case_id,
                passed=False,
                duration_seconds=time.perf_counter() - started,
                failure_kind=FailureKind.NON_DETERMINISTIC,
                message="candidate produced different results for the same input",
                input=input_bytes,
                actual_output=candidate.stdout,
                expected_output=expected_output,
                oracle_output=None if oracle is None else oracle.stdout,
                actual_stderr=repeated.stderr,
                actual_exit_code=candidate.exit_code,
                expected_exit_code=expected_exit_code,
                oracle_exit_code=None if oracle is None else oracle.exit_code,
                seed=seed,
                generator_hash=generator_hash,
                input_hash=_hash_bytes(input_bytes),
            )

    match, message = await _compare(
        workspace,
        spec,
        candidate_output=candidate.stdout,
        expected_output=expected_output,
    )
    return CaseResult(
        case_id=case_id,
        passed=match,
        duration_seconds=time.perf_counter() - started,
        failure_kind=None if match else FailureKind.OUTPUT_MISMATCH,
        message="" if match else message,
        input=input_bytes,
        actual_output=candidate.stdout,
        expected_output=expected_output,
        oracle_output=None if oracle is None else oracle.stdout,
        actual_stderr=candidate.stderr,
        actual_exit_code=candidate.exit_code,
        expected_exit_code=expected_exit_code,
        oracle_exit_code=None if oracle is None else oracle.exit_code,
        seed=seed,
        generator_hash=generator_hash,
        input_hash=_hash_bytes(input_bytes),
    )


async def _compare(
    workspace: Path,
    spec: CorrectnessSpec,
    *,
    candidate_output: bytes,
    expected_output: bytes,
) -> tuple[bool, str]:
    if spec.comparison is ComparisonMode.EXACT:
        matched = candidate_output == expected_output
    elif spec.comparison is ComparisonMode.LINE_TRIM:
        matched = _line_trim(candidate_output) == _line_trim(expected_output)
    elif spec.comparison is ComparisonMode.TOKEN_NORMALIZED:
        matched = _token_normalize(candidate_output) == _token_normalize(expected_output)
    elif spec.comparison in {ComparisonMode.FLOAT_ABSOLUTE, ComparisonMode.FLOAT_RELATIVE}:
        matched = _compare_floats(
            candidate_output,
            expected_output,
            relative=spec.comparison is ComparisonMode.FLOAT_RELATIVE,
            tolerance=spec.float_tolerance,
        )
    else:
        checker = await _run_checker(workspace, spec, candidate_output, expected_output)
        return checker.exit_code == 0, "" if checker.exit_code == 0 else "checker rejected output"
    return matched, "" if matched else "candidate output did not match expected output"


def _line_trim(data: bytes) -> bytes:
    return b"\n".join(line.rstrip() for line in data.splitlines())


def _token_normalize(data: bytes) -> bytes:
    return b" ".join(data.split())


def _compare_floats(
    actual: bytes,
    expected: bytes,
    *,
    relative: bool,
    tolerance: float,
) -> bool:
    try:
        actual_values = [float(token) for token in actual.split()]
        expected_values = [float(token) for token in expected.split()]
    except ValueError:
        return False
    if len(actual_values) != len(expected_values):
        return False
    for actual_value, expected_value in zip(actual_values, expected_values, strict=True):
        difference = abs(actual_value - expected_value)
        if relative:
            denominator = max(abs(expected_value), 1e-300)
            if difference / denominator > tolerance:
                return False
        elif difference > tolerance:
            return False
    return True


async def _run_checker(
    workspace: Path,
    spec: CorrectnessSpec,
    candidate_output: bytes,
    expected_output: bytes,
) -> _ProcessResult:
    with tempfile.TemporaryDirectory(dir=workspace) as directory:
        temp = Path(directory)
        candidate_path = temp / "candidate.out"
        expected_path = temp / "expected.out"
        candidate_path.write_bytes(candidate_output)
        expected_path.write_bytes(expected_output)
        command = tuple(
            token.format(
                workspace=workspace,
                candidate=candidate_path,
                expected=expected_path,
            )
            for token in spec.checker_command
        )
        return await _run_process(
            command,
            workspace=workspace,
            input_bytes=b"",
            timeout_seconds=spec.timeout_seconds,
        )


async def _run_process(
    command: tuple[str, ...],
    *,
    workspace: Path,
    input_bytes: bytes,
    timeout_seconds: int,
    extra_env: dict[str, str] | None = None,
) -> _ProcessResult:
    runner = _SANDBOX_RUNNER.get() or SandboxProcessRunner()
    result = await runner.run(
        command,
        cwd=workspace,
        timeout_seconds=timeout_seconds,
        input_bytes=input_bytes,
        extra_env=extra_env,
    )
    return _ProcessResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_seconds=result.duration_seconds,
        timed_out=result.timed_out,
        start_failed=result.start_failed,
    )


def _expand_command(command: tuple[str, ...], workspace: Path) -> tuple[str, ...]:
    return tuple(token.format(workspace=workspace) for token in command)


def _failed_case(
    case_id: str,
    input_bytes: bytes,
    process: _ProcessResult,
    failure_kind: FailureKind,
    message: str,
    seed: int | None,
    generator_hash: str | None,
    expected_exit_code: int,
) -> CaseResult:
    return CaseResult(
        case_id=case_id,
        passed=False,
        duration_seconds=process.duration_seconds,
        failure_kind=failure_kind,
        message=message,
        input=input_bytes,
        actual_output=process.stdout,
        actual_stderr=process.stderr,
        actual_exit_code=process.exit_code,
        expected_exit_code=expected_exit_code,
        seed=seed,
        generator_hash=generator_hash,
        input_hash=_hash_bytes(input_bytes),
    )


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_payload(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
