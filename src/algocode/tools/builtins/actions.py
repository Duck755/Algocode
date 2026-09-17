"""Mutation, execution, and control tools."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from algocode.benchmark.spec import BenchmarkSpec, load_benchmark_spec
from algocode.correctness.spec import CorrectnessSpec, load_correctness_spec
from algocode.domain.model import TaskPhase
from algocode.languages.cpp import run_cpp_contract_test
from algocode.project_layout import ProjectLayout
from algocode.runtime.planning import OptimizationPlan
from algocode.tools.types import ToolContext, ToolDefinition, ToolResult
from algocode.workspace import GitRepository

_PATCH_PATH = re.compile(r"^(?:--- a/|\+\+\+ b/)(.+)$", re.MULTILINE)


async def create_candidate(context: ToolContext, arguments: dict[str, object]) -> ToolResult:
    if context.phase is not TaskPhase.GENERATE_CANDIDATE:
        return ToolResult(
            status="error",
            summary="create_candidate is only allowed in generate_candidate",
        )
    if context.candidate_service is None:
        return ToolResult(status="error", summary="candidate service is not available")
    if context.candidate_id is not None:
        candidate = await context.candidate_service.get(context.candidate_id)
    else:
        candidate = await context.candidate_service.create(
            context.task.id,
            source_workspace=context.candidate_base_workspace,
            parent_candidate_id=context.candidate_parent_candidate_id,
        )
    return ToolResult(
        status="success",
        summary=f"candidate {candidate.id} is ready",
        structured={
            "candidate_id": str(candidate.id),
            "workspace_ref": candidate.workspace_ref,
            "status": candidate.status.value,
        },
    )


async def apply_patch(context: ToolContext, arguments: dict[str, object]) -> ToolResult:
    if context.phase is not TaskPhase.IMPLEMENT:
        return ToolResult(status="error", summary="apply_patch is only allowed in implement")
    if context.candidate_id is None:
        return ToolResult(status="error", summary="apply_patch is only allowed in a candidate")
    patch = str(arguments.get("patch", ""))
    if not patch:
        return ToolResult(status="error", summary="patch must not be empty")
    changed_paths = tuple(dict.fromkeys(_PATCH_PATH.findall(patch)))
    protected = tuple(
        path
        for path in changed_paths
        if any(
            path == pattern.rstrip("/") or path.startswith(f"{pattern.rstrip('/')}/")
            for pattern in context.protected_files
        )
    )
    if protected:
        return ToolResult(
            status="error",
            summary=f"patch modifies protected files: {', '.join(protected)}",
        )
    repository = await GitRepository.discover(context.workspace)
    check = await repository.apply_patch(patch.encode(), check_only=True)
    if check.exit_code != 0:
        return ToolResult(
            status="error",
            summary=f"patch precheck failed: {check.stderr.decode(errors='replace')}",
        )
    applied = await repository.apply_patch(patch.encode())
    if applied.exit_code != 0:
        return ToolResult(
            status="error",
            summary=f"patch failed: {applied.stderr.decode(errors='replace')}",
        )
    snapshot = await repository.capture_snapshot(context.workspace)
    return ToolResult(
        status="success",
        summary=f"applied patch to {len(changed_paths)} files",
        structured={
            "applied_files": list(changed_paths),
            "patch_hash": snapshot.snapshot_hash,
            "snapshot_hash": snapshot.snapshot_hash,
        },
    )


async def build(context: ToolContext, arguments: dict[str, object]) -> ToolResult:
    if context.language_registry is None or context.artifact_store is None:
        return ToolResult(status="error", summary="build services are not available")
    detected = await context.language_registry.detect(context.workspace)
    language = detected.primary_language
    if language is None:
        return ToolResult(status="error", summary="no supported language was detected")
    adapter = context.language_registry.adapter_for(language)
    await adapter.prepare(context.workspace, context.build_profile)
    result = await adapter.build(context.workspace, context.build_profile)
    output_ref = await context.artifact_store.put(
        result.output,
        kind="tool-build-output",
        mime_type="text/plain",
        metadata={"task_id": str(context.task.id), "phase": context.phase.value},
    )
    return ToolResult(
        status="success" if result.succeeded else "error",
        summary=f"build exited with {result.exit_code}",
        structured={
            "exit_code": result.exit_code,
            "duration_seconds": result.duration_seconds,
            "commands": [list(command) for command in result.commands],
        },
        artifact_refs=(output_ref,),
    )


async def run_correctness(context: ToolContext, arguments: dict[str, object]) -> ToolResult:
    if context.phase is not TaskPhase.VERIFY:
        return ToolResult(status="error", summary="run_correctness is only allowed in verify")
    if context.correctness_service is None or context.candidate_id is None:
        return ToolResult(status="error", summary="candidate correctness is not available")
    spec_path = arguments.get("spec_path")
    if spec_path is not None:
        try:
            path = _workspace_file(context.workspace, str(spec_path))
            spec = load_correctness_spec(path)
        except (OSError, ValueError) as exc:
            return ToolResult(status="error", summary=f"invalid correctness spec_path: {exc}")
    else:
        raw_spec = arguments.get("spec")
        if not isinstance(raw_spec, dict):
            return ToolResult(status="error", summary="spec or spec_path is required")
        raw_spec = _normalize_correctness_spec(raw_spec)
        if "seed" in arguments:
            raw_spec = {**raw_spec, "seed": arguments["seed"]}
        spec = CorrectnessSpec.model_validate(raw_spec)
    run, result = await context.correctness_service.run_target(
        context.task.id,
        spec,
        target_kind="candidate",
        target_id=context.candidate_id,
        workspace_ref=context.workspace,
    )
    return ToolResult(
        status="success" if result.passed else "error",
        summary=f"correctness {'passed' if result.passed else 'failed'}",
        structured={
            "result_id": run.id,
            "failure_kind": (
                result.failure_kind.value if result.failure_kind is not None else None
            ),
            "passed_cases": result.passed_cases,
            "failed_cases": result.failed_cases,
        },
        artifact_refs=tuple(ref for ref in (run.result_ref,) if ref is not None),
    )


async def run_candidate_check(context: ToolContext, arguments: dict[str, object]) -> ToolResult:
    if context.phase is not TaskPhase.IMPLEMENT:
        return ToolResult(
            status="error",
            summary="run_candidate_check is only allowed in implement",
        )
    if context.candidate_id is None or context.correctness_service is None:
        return ToolResult(status="error", summary="candidate check requires an active candidate")

    layout = ProjectLayout.from_root(context.workspace)
    correctness_path = layout.correctness_spec()
    if not correctness_path.is_file():
        return ToolResult(status="error", summary="correctness specification is not configured")

    try:
        repository = await GitRepository.discover(context.workspace)
        spec = load_correctness_spec(correctness_path)
    except (OSError, ValueError) as exc:
        return ToolResult(status="error", summary=f"candidate check setup failed: {exc}")

    run, result = await context.correctness_service.run_target(
        context.task.id,
        spec,
        target_kind="candidate",
        target_id=context.candidate_id,
        workspace_ref=context.workspace,
        record_candidate_status=False,
    )
    if not result.passed:
        snapshot = await repository.capture_snapshot(context.workspace)
        return ToolResult(
            status="error",
            summary="candidate correctness check failed",
            structured={
                "snapshot_hash": snapshot.snapshot_hash,
                "correctness_result_id": run.id,
                "failure_kind": (
                    result.failure_kind.value if result.failure_kind is not None else None
                ),
                "passed_cases": result.passed_cases,
                "failed_cases": result.failed_cases,
                "failure_details": [
                    _case_failure_payload(case) for case in result.cases if not case.passed
                ],
            },
            artifact_refs=tuple(ref for ref in (run.result_ref,) if ref is not None),
        )

    contract_required = layout.contract_test() is not None
    contract_stdout = ""
    if contract_required:
        contract_result = await _run_contract_test(context, layout)
        if contract_result.status != "success":
            snapshot = await repository.capture_snapshot(context.workspace)
            return ToolResult(
                status="error",
                summary="candidate contract check failed",
                structured={
                    "snapshot_hash": snapshot.snapshot_hash,
                    "correctness_result_id": run.id,
                    "contract": contract_result.structured,
                },
                truncated=contract_result.truncated,
            )
        contract_stdout = str(contract_result.structured.get("stdout", ""))

    snapshot = await repository.capture_snapshot(context.workspace)
    return ToolResult(
        status="success",
        summary="candidate checks passed",
        structured={
            "snapshot_hash": snapshot.snapshot_hash,
            "correctness_result_id": run.id,
            "contract_passed": contract_required,
            "contract_stdout": contract_stdout,
        },
        artifact_refs=tuple(ref for ref in (run.result_ref,) if ref is not None),
    )


async def run_benchmark(context: ToolContext, arguments: dict[str, object]) -> ToolResult:
    if context.phase is not TaskPhase.BENCHMARK:
        return ToolResult(status="error", summary="run_benchmark is only allowed in benchmark")
    if (
        context.benchmark_service is None
        or context.candidate_id is None
        or context.correctness_result_id is None
    ):
        return ToolResult(
            status="error",
            summary="candidate benchmark requires passed correctness",
        )
    spec_path = arguments.get("spec_path")
    if spec_path is not None:
        try:
            path = _workspace_file(context.workspace, str(spec_path))
            spec = load_benchmark_spec(path)
        except (OSError, ValueError) as exc:
            return ToolResult(status="error", summary=f"invalid benchmark spec_path: {exc}")
    else:
        raw_spec = arguments.get("spec")
        if not isinstance(raw_spec, dict):
            return ToolResult(status="error", summary="spec or spec_path is required")
        spec = BenchmarkSpec.model_validate(raw_spec)
    run, result, comparison = await context.benchmark_service.run_candidate(
        context.task.id,
        context.candidate_id,
        context.workspace,
        context.correctness_result_id,
        spec,
        build_profile=context.build_profile,
    )
    return ToolResult(
        status="success" if result.valid else "error",
        summary=f"benchmark {'valid' if result.valid else 'invalid'}",
        structured={
            "run_id": run.id,
            "improvement_percent": comparison.improvement_percent,
            "comparison_valid": comparison.valid,
            "baseline_median": comparison.baseline_median,
            "candidate_median": comparison.candidate_median,
        },
        artifact_refs=tuple(ref for ref in (run.result_ref, run.comparison_ref) if ref is not None),
    )


async def run_contract(context: ToolContext, arguments: dict[str, object]) -> ToolResult:
    if context.phase is not TaskPhase.VERIFY:
        return ToolResult(status="error", summary="run_contract is only allowed in verify")
    if context.language_registry is None:
        return ToolResult(status="error", summary="contract runner is unavailable")
    layout = ProjectLayout.from_root(context.workspace)
    contract_path = layout.contract_test()
    if contract_path is None:
        return ToolResult(
            status="error",
            summary="contract test is not configured",
        )
    runner = context.language_registry.sandbox_runner
    if contract_path.suffix.lower() == ".cpp":
        contract_result = await run_cpp_contract_test(
            context.workspace,
            contract_path,
            runner,
        )
        return ToolResult(
            status="success" if contract_result.passed else "error",
            summary=(
                "contract tests passed" if contract_result.passed else "contract tests failed"
            ),
            structured={
                "exit_code": contract_result.candidate_exit_code,
                "timed_out": False,
                "stdout": contract_result.stdout.decode(errors="replace"),
                "stderr": contract_result.stderr.decode(errors="replace"),
                "message": contract_result.message,
            },
            truncated=contract_result.truncated,
        )
    result = await runner.run(
        (sys.executable, layout.relative(contract_path)),
        cwd=context.workspace,
        timeout_seconds=60,
        input_bytes=b"",
    )
    return ToolResult(
        status="success" if result.exit_code == 0 and not result.timed_out else "error",
        summary="contract tests passed" if result.exit_code == 0 else "contract tests failed",
        structured={
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "stdout": result.stdout.decode(errors="replace"),
            "stderr": result.stderr.decode(errors="replace"),
        },
        truncated=result.truncated,
    )


async def _run_contract_test(context: ToolContext, layout: ProjectLayout) -> ToolResult:
    contract_path = layout.contract_test()
    if contract_path is None:
        return ToolResult(
            status="error",
            summary="contract test is not configured",
        )
    if context.language_registry is None:
        return ToolResult(status="error", summary="contract runner is unavailable")
    runner = context.language_registry.sandbox_runner
    if contract_path.suffix.lower() == ".cpp":
        contract_result = await run_cpp_contract_test(
            context.workspace,
            contract_path,
            runner,
        )
        return ToolResult(
            status="success" if contract_result.passed else "error",
            summary=(
                "contract tests passed" if contract_result.passed else "contract tests failed"
            ),
            structured={
                "exit_code": contract_result.candidate_exit_code,
                "timed_out": False,
                "stdout": contract_result.stdout.decode(errors="replace"),
                "stderr": contract_result.stderr.decode(errors="replace"),
                "message": contract_result.message,
            },
            truncated=contract_result.truncated,
        )
    result = await runner.run(
        (sys.executable, layout.relative(contract_path)),
        cwd=context.workspace,
        timeout_seconds=60,
        input_bytes=b"",
    )
    return ToolResult(
        status="success" if result.exit_code == 0 and not result.timed_out else "error",
        summary="contract tests passed" if result.exit_code == 0 else "contract tests failed",
        structured={
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "stdout": result.stdout.decode(errors="replace"),
            "stderr": result.stderr.decode(errors="replace"),
        },
        truncated=result.truncated,
    )


def _case_failure_payload(case) -> dict[str, object]:
    return {
        "case_id": case.case_id,
        "passed": case.passed,
        "failure_kind": (case.failure_kind.value if case.failure_kind is not None else None),
        "message": case.message,
        "actual_output": case.actual_output.decode(errors="replace"),
        "expected_output": (
            case.expected_output.decode(errors="replace")
            if case.expected_output is not None
            else None
        ),
        "actual_stderr": case.actual_stderr.decode(errors="replace"),
        "actual_exit_code": case.actual_exit_code,
        "expected_exit_code": case.expected_exit_code,
    }


def _normalize_correctness_spec(raw_spec: dict[str, object]) -> dict[str, object]:
    normalized = dict(raw_spec)
    normalized.setdefault("mode", "cases")
    normalized.setdefault("comparison", "line-trim")
    raw_cases = normalized.get("cases")
    if not isinstance(raw_cases, list):
        return normalized
    cases: list[dict[str, object]] = []
    for index, raw_case in enumerate(raw_cases):
        if not isinstance(raw_case, dict):
            continue
        case = dict(raw_case)
        expected = case.pop("expected", None)
        if isinstance(expected, dict):
            case = {**expected, **case}
        case["id"] = str(case.get("id") or case.get("name") or f"case_{index + 1}")
        if "input" not in case and "stdin" in case:
            case["input"] = case["stdin"]
        expected_output = case.get("expected_output")
        for alias in ("expected_stdout", "stdout", "expect_stdout"):
            expected_output = expected_output or case.get(alias)
        if expected_output is not None:
            case["expected_output"] = str(expected_output)
        expected_exit = case.get("expected_exit_code")
        for alias in ("exit_code", "expect_exit_code"):
            expected_exit = expected_exit if expected_exit is not None else case.get(alias)
        if expected_exit is not None:
            case["expected_exit_code"] = int(expected_exit)
        cases.append(
            {
                key: case[key]
                for key in (
                    "id",
                    "input",
                    "expected_output",
                    "expected_exit_code",
                    "args",
                    "timeout_seconds",
                )
                if key in case
            }
        )
    normalized["cases"] = cases
    return normalized


def _workspace_file(workspace: Path, relative_path: str) -> Path:
    root = workspace.resolve()
    target = (root / relative_path).resolve()
    if not target.is_relative_to(root):
        raise ValueError("spec_path escapes the candidate workspace")
    if not target.is_file():
        raise ValueError(f"spec file not found: {relative_path}")
    return target


async def submit_phase_result(context: ToolContext, arguments: dict[str, object]) -> ToolResult:
    phase = str(arguments.get("phase", ""))
    if phase != context.phase.value:
        return ToolResult(status="error", summary="submitted phase does not match current phase")
    status = str(arguments.get("status", ""))
    status = {
        "success": "completed",
        "done": "completed",
        "ok": "completed",
        "failed": "blocked",
        "continue": "completed",
        "failure": "blocked",
        "error": "blocked",
    }.get(status, status)
    if status not in {"completed", "blocked"}:
        return ToolResult(status="error", summary="invalid phase result status")
    result = arguments.get("result", {})
    if not isinstance(result, dict):
        return ToolResult(status="error", summary="phase result payload must be an object")
    return ToolResult(
        status="success",
        summary=str(arguments.get("summary", "")),
        structured={
            "phase": phase,
            "status": status,
            "summary": str(arguments.get("summary", "")),
            "findings": arguments.get("findings", []),
            "blockers": arguments.get("blockers", []),
            "result": result,
        },
    )


async def submit_optimization_plan(
    context: ToolContext,
    arguments: dict[str, object],
) -> ToolResult:
    if context.phase is not TaskPhase.PLAN:
        return ToolResult(
            status="error",
            summary="submit_optimization_plan is only allowed in plan",
        )
    try:
        plan = OptimizationPlan.model_validate(arguments)
    except ValueError as exc:
        return ToolResult(
            status="error",
            summary=f"invalid optimization plan: {exc}",
            structured={"validation_errors": str(exc), "phase": context.phase.value},
        )
    return ToolResult(
        status="success",
        summary=plan.summary,
        structured={
            "phase": context.phase.value,
            "status": "completed",
            "optimization_plan": plan.model_dump(by_alias=True, mode="json"),
        },
    )


def register_action_tools(registry) -> None:
    registry.register(
        ToolDefinition(
            name="create_candidate",
            description="Create or reuse the isolated candidate workspace for the task.",
            input_schema={},
            effects="control",
            idempotent=True,
            parallelizable=False,
        ),
        create_candidate,
    )
    registry.register(
        ToolDefinition(
            name="apply_patch",
            description="Apply a unified diff to the candidate workspace.",
            input_schema={"patch": {"type": "string", "required": True}},
            effects="write",
            idempotent=False,
            parallelizable=False,
            permission="allow",
        ),
        apply_patch,
    )
    registry.register(
        ToolDefinition(
            name="build",
            timeout_seconds=300,
            description="Build the current candidate workspace.",
            input_schema={},
            effects="execute",
            idempotent=False,
            parallelizable=False,
        ),
        build,
    )
    registry.register(
        ToolDefinition(
            name="run_correctness",
            timeout_seconds=300,
            description="Run a correctness suite for the current candidate.",
            input_schema={
                "spec": {"type": "object", "required": False},
                "spec_path": {"type": "string", "required": False},
                "seed": {"type": "integer", "required": False},
            },
            effects="execute",
            idempotent=False,
            parallelizable=False,
        ),
        run_correctness,
    )
    registry.register(
        ToolDefinition(
            name="run_candidate_check",
            timeout_seconds=300,
            description=(
                "Run the project correctness and contract checks before an "
                "implement phase can be submitted."
            ),
            input_schema={},
            effects="execute",
            idempotent=False,
            parallelizable=False,
        ),
        run_candidate_check,
    )
    registry.register(
        ToolDefinition(
            name="run_benchmark",
            timeout_seconds=900,
            description="Compare the current candidate using a benchmark spec.",
            input_schema={
                "spec": {"type": "object", "required": False},
                "spec_path": {"type": "string", "required": False},
            },
            effects="execute",
            idempotent=False,
            parallelizable=False,
        ),
        run_benchmark,
    )
    registry.register(
        ToolDefinition(
            name="run_contract",
            timeout_seconds=300,
            description="Run the generated behavior contract test in the candidate workspace.",
            input_schema={},
            effects="execute",
            idempotent=False,
            parallelizable=False,
        ),
        run_contract,
    )
    registry.register(
        ToolDefinition(
            name="submit_phase_result",
            description="Submit the result of the current agent phase.",
            input_schema={
                "phase": {"type": "string", "required": True},
                "status": {
                    "type": "string",
                    "enum": ["completed", "blocked"],
                    "required": True,
                },
                "summary": {"type": "string", "required": True},
                "result": {"type": "object", "required": False},
            },
            effects="control",
            idempotent=True,
            parallelizable=False,
        ),
        submit_phase_result,
    )
    registry.register(
        ToolDefinition(
            name="submit_optimization_plan",
            description=(
                "Submit the final OptimizationPlan for the PLAN phase. Keep the plan compact: "
                "at most 5 steps and do not copy long contract text."
            ),
            input_schema={
                "summary": {"type": "string", "required": True},
                "strategy": {"type": "string", "required": True},
                "steps": {
                    "type": "array",
                    "required": True,
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "description": {"type": "string"},
                            "files": {"type": "array", "items": {"type": "string"}},
                            "verification": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["id", "description"],
                    },
                },
                "constraints": {"type": "array", "items": {"type": "string"}},
                "protectedFiles": {"type": "array", "items": {"type": "string"}},
                "benchmarkPlan": {"type": "array", "items": {"type": "string"}},
                "risks": {"type": "array", "items": {"type": "string"}},
                "retryDecision": {
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["continue", "pivot", "rollback"],
                        },
                        "basedOnAttempt": {"type": "integer"},
                        "parentAttempt": {"type": "integer"},
                        "directionId": {"type": "string"},
                        "directionState": {
                            "type": "string",
                            "enum": ["active", "exhausted", "abandoned"],
                        },
                        "reason": {"type": "string"},
                        "preserveChanges": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "mode",
                        "basedOnAttempt",
                        "parentAttempt",
                        "directionId",
                        "reason",
                    ],
                },
            },
            argument_model=OptimizationPlan,
            effects="control",
            idempotent=True,
            parallelizable=False,
        ),
        submit_optimization_plan,
    )
