"""Persist project contract and current task state beside the project."""

from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from algocode.project_layout import ProjectLayout

STATE_DIR = ".algocode"
CURRENT_TASK_FILE = "current-task.json"
CONTRACT_FILE = "contract.json"
TASK_SUMMARY_FILE = "task.txt"


def current_task_path(project_root: str | Path) -> Path:
    return Path(project_root).resolve() / STATE_DIR / CURRENT_TASK_FILE


def find_current_task(start: str | Path | None = None) -> dict[str, Any] | None:
    current = Path(start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        path = current_task_path(directory)
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None
    return None


def write_contract(
    *,
    project_root: str | Path,
    project_id: str,
    language: str,
    git_revision: str,
    objective: str,
    entrypoints: tuple[str, ...],
    public_api: tuple[str, ...],
) -> Path:
    root = Path(project_root).resolve()
    path = ProjectLayout.from_root(root).contract_path
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(UTC).isoformat(),
        "project": {
            "projectId": project_id,
            "root": str(root),
            "language": language,
            "gitRevision": git_revision,
        },
        "purpose": objective,
        "entrypoints": list(entrypoints),
        "publicApi": list(public_api),
        "correctnessSpec": ".algocode/oracle/correctness.yaml",
        "benchmarkSpec": ".algocode/benchmarks/benchmark.yaml",
        "invariants": [
            "Public API signatures and documented behavior must remain stable.",
            "Configuration fields must retain their documented semantics.",
            "Errors and state transitions must remain compatible unless explicitly changed.",
        ],
        "mustNotChange": [
            ".algocode/oracle/",
            ".algocode/benchmarks/",
            ".algocode/config.yaml",
        ],
        "unknowns": [],
        "confidence": 0.5,
        "contractSource": "deterministic-bootstrap",
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def write_bootstrap_state(
    *,
    project_root: str | Path,
    data_dir: str | Path,
    project_id: str,
    project_language: str,
    git_revision: str,
    task_id: str,
    objective: str,
    baseline_id: str,
    correctness_result_id: str | None,
    correctness_status: str | None,
    benchmark_run_id: str | None,
    benchmark_valid: bool | None,
    generated_files: tuple[str, ...],
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    state_dir = root / STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schemaVersion": 1,
        "updatedAt": datetime.now(UTC).isoformat(),
        "projectId": project_id,
        "root": str(root),
        "language": project_language,
        "gitRevision": git_revision,
        "dataDir": str(Path(data_dir).expanduser()),
        "databasePath": str(Path(data_dir).expanduser() / "algocode.db"),
        "taskId": task_id,
        "objective": objective,
        "baselineId": baseline_id,
        "correctness": {
            "specPath": ".algocode/oracle/correctness.yaml",
            "resultId": correctness_result_id,
            "status": correctness_status,
        },
        "benchmark": {
            "specPath": ".algocode/benchmarks/benchmark.yaml",
            "runId": benchmark_run_id,
            "valid": benchmark_valid,
        },
        "candidateId": None,
        "experimentId": None,
        "contractPath": f"{STATE_DIR}/{CONTRACT_FILE}",
        "taskSummaryPath": f"{STATE_DIR}/{TASK_SUMMARY_FILE}",
        "generatedFiles": list(generated_files),
        "nextCommand": (f"algocode optimize {task_id} --provider default --model default"),
    }
    current_task_path(root).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_task_summary(root, payload)
    return payload


def update_current_task(
    *,
    project_root: str | Path,
    **updates: Any,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    path = current_task_path(root)
    payload = find_current_task(root) or {}
    payload.update(updates)
    payload["updatedAt"] = datetime.now(UTC).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_task_summary(root, payload)
    return payload


def write_task_summary(project_root: str | Path, payload: dict[str, Any]) -> Path:
    root = Path(project_root).resolve()
    path = root / STATE_DIR / TASK_SUMMARY_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    correctness = payload.get("correctness") or {}
    benchmark = payload.get("benchmark") or {}
    lines = [
        f"Project: {payload.get('projectId', '')}",
        f"Root: {payload.get('root', '')}",
        f"Language: {payload.get('language', '')}",
        f"Git revision: {payload.get('gitRevision', '')}",
        "",
        f"Task: {payload.get('taskId', '')}",
        f"Objective: {payload.get('objective', '')}",
        f"Contract: {payload.get('contractPath', '')}",
        "",
        f"Baseline: {payload.get('baselineId', '')}",
        f"Correctness spec: {correctness.get('specPath', '')}",
        f"Correctness result: {correctness.get('resultId', '')}",
        f"Correctness status: {correctness.get('status', '')}",
        f"Benchmark spec: {benchmark.get('specPath', '')}",
        f"Benchmark run: {benchmark.get('runId', '')}",
        f"Benchmark valid: {benchmark.get('valid', '')}",
        f"Benchmark improvement percent: {benchmark.get('improvementPercent', '')}",
        "",
        f"Candidate: {payload.get('candidateId', '') or ''}",
        f"Experiment: {payload.get('experimentId', '') or ''}",
        f"Status: {payload.get('status', '') or ''}",
        f"Summary: {payload.get('summary', '') or ''}",
        "",
        "Next command:",
        str(payload.get("nextCommand", "")),
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def discover_python_public_api(root: str | Path) -> tuple[str, ...]:
    project_root = Path(root).resolve()
    symbols: set[str] = set()
    for path in sorted(project_root.glob("*.py")):
        if path.name == "__init__.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        for node in tree.body:
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) and not node.name.startswith("_"):
                symbols.add(node.name)
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                symbols.add(node.name)
                for child in node.body:
                    if isinstance(
                        child, (ast.FunctionDef, ast.AsyncFunctionDef)
                    ) and not child.name.startswith("_"):
                        symbols.add(f"{node.name}.{child.name}")
    return tuple(sorted(symbols))
