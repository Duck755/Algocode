"""Mutation, execution, and control tools."""

from __future__ import annotations

import re

from algocode.benchmark.spec import BenchmarkSpec
from algocode.correctness.spec import CorrectnessSpec
from algocode.domain.model import TaskPhase
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
        candidate = await context.candidate_service.create(context.task.id)
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
    raw_spec = arguments.get("spec")
    if not isinstance(raw_spec, dict):
        return ToolResult(status="error", summary="spec must be an object")
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
    raw_spec = arguments.get("spec")
    if not isinstance(raw_spec, dict):
        return ToolResult(status="error", summary="spec must be an object")
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
        "failure": "blocked",
        "error": "blocked",
    }.get(status, status)
    if status not in {"continue", "completed", "blocked"}:
        return ToolResult(status="error", summary="invalid phase result status")
    return ToolResult(
        status="success",
        summary=str(arguments.get("summary", "")),
        structured={
            "phase": phase,
            "status": status,
            "summary": str(arguments.get("summary", "")),
            "findings": arguments.get("findings", []),
            "blockers": arguments.get("blockers", []),
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
            description="Run a correctness suite for the current candidate.",
            input_schema={
                "spec": {"type": "object", "required": True},
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
            name="run_benchmark",
            description="Compare the current candidate using a benchmark spec.",
            input_schema={"spec": {"type": "object", "required": True}},
            effects="execute",
            idempotent=False,
            parallelizable=False,
        ),
        run_benchmark,
    )
    registry.register(
        ToolDefinition(
            name="submit_phase_result",
            description="Submit the result of the current agent phase.",
            input_schema={
                "phase": {"type": "string", "required": True},
                "status": {
                    "type": "string",
                    "enum": ["continue", "completed", "blocked"],
                    "required": True,
                },
                "summary": {"type": "string", "required": True},
            },
            effects="control",
            idempotent=True,
            parallelizable=False,
        ),
        submit_phase_result,
    )
