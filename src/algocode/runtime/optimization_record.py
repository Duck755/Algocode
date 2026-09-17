"""Durable optimization-run records and retry history rendering."""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from algocode.security import SecretRedactor

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_HISTORY_DIFF_CHARS = 8_000


class OptimizationRecordStore:
    """Persist full optimization attempts and render compact retry history."""

    def __init__(
        self,
        root: str | Path,
        *,
        redactor: SecretRedactor | None = None,
    ) -> None:
        self.root = Path(root).expanduser()
        self._redactor = redactor or SecretRedactor()
        self._lock = asyncio.Lock()

    async def record(self, *, task_id: str, payload: dict[str, Any]) -> Path:
        safe_task = _SAFE_NAME.sub("_", task_id).strip("._") or "unknown"
        scope_dir = self.root / safe_task
        async with self._lock:
            scope_dir.mkdir(parents=True, exist_ok=True)
            attempt = len(tuple(scope_dir.glob("[0-9][0-9][0-9][0-9]-*.json"))) + 1
            record = {
                "schema_version": 1,
                "task_id": task_id,
                "attempt": attempt,
                "recorded_at": datetime.now(UTC).isoformat(),
                **self._redactor.redact_value(payload),
            }
            stem = f"{attempt:04d}-{_safe_command(record.get('command'))}"
            json_path = scope_dir / f"{stem}.json"
            markdown_path = scope_dir / f"{stem}.md"
            self._write_text_atomic(
                json_path,
                json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            )
            self._write_text_atomic(markdown_path, _render_record_markdown(record) + "\n")
            self._append_index(scope_dir, stem, record)
            return json_path

    def list_records(self, *, task_id: str) -> tuple[dict[str, Any], ...]:
        safe_task = _SAFE_NAME.sub("_", task_id).strip("._") or "unknown"
        scope_dir = self.root / safe_task
        if not scope_dir.is_dir():
            return ()
        records: list[dict[str, Any]] = []
        for path in sorted(scope_dir.glob("[0-9][0-9][0-9][0-9]-*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                records.append(payload)
        return tuple(records)

    def render_history(self, *, task_id: str, limit: int = 3) -> str:
        records = self.list_records(task_id=task_id)
        if not records:
            return ""
        selected = records[-max(1, limit) :]
        selected = records[-max(1, limit) :]
        best = max(
            (
                record
                for record in records
                if _optional_float(record.get("improvement_percent")) is not None
            ),
            key=lambda record: _optional_float(record.get("improvement_percent")) or float("-inf"),
            default=None,
        )
        lines = [
            "# Optimization History",
            "",
            "This is a retry. Use these records to avoid repeating failed or non-improving",
            "optimization strategies. The objective and contract remain unchanged.",
            "",
        ]
        if best is not None:
            lines.extend(
                [
                    "## Global Best",
                    "",
                    f"- attempt: {best.get('attempt')}",
                    f"- improvement_percent: {best.get('improvement_percent')}",
                    f"- candidate_id: {best.get('candidate_id')}",
                    "- role: scoreboard only; do not automatically use this as retry parent",
                    "",
                ]
            )
        lines.extend(
            [
                "## Decision Cursor",
                "",
                f"- last_attempt: {records[-1].get('attempt')}",
                "- Retry decisions must be based on last_attempt, not global best.",
                "",
                "## Attempts",
                "",
            ]
        )
        exhausted: list[str] = []
        abandoned: list[str] = []
        for index, record in enumerate(records):
            if index == 0:
                continue
            previous = records[index - 1]
            direction = previous.get("direction_id")
            if not isinstance(direction, str):
                continue
            mode = record.get("retry_mode")
            if mode == "pivot" and direction not in exhausted:
                exhausted.append(direction)
            elif mode == "rollback" and direction not in abandoned:
                abandoned.append(direction)
        lines.extend(
            [
                "## Direction State",
                "",
                f"- current_direction: {records[-1].get('direction_id')}",
                f"- exhausted_directions: {exhausted}",
                f"- abandoned_directions: {abandoned}",
                "- Only pivot when the last direction is genuinely exhausted.",
                "- Do not enter an exhausted direction again.",
                "",
            ]
        )
        for record in selected:
            lines.extend(
                [
                    f"## Attempt {record.get('attempt', '?')}",
                    "",
                    f"- command: {record.get('command', 'optimize')}",
                    f"- status: {record.get('status', 'unknown')}",
                    f"- completed_phases: {record.get('completed_phases', [])}",
                    f"- candidate_id: {record.get('candidate_id', None)}",
                    f"- improvement_percent: {record.get('improvement_percent', None)}",
                    f"- benchmark_valid: {record.get('benchmark_valid', None)}",
                    f"- summary: {record.get('summary', '')}",
                    "",
                ]
            )
            lines.extend(
                [
                    f"- retry_mode: {record.get('retry_mode', None)}",
                    f"- based_on_attempt: {record.get('based_on_attempt', None)}",
                    f"- parent_attempt: {record.get('parent_attempt', 0)}",
                    f"- direction_id: {record.get('direction_id', None)}",
                    f"- direction_state: {record.get('direction_state', None)}",
                    f"- delta_vs_parent: {record.get('delta_vs_parent', None)}",
                    f"- delta_vs_global_best: {record.get('delta_vs_global_best', None)}",
                    "",
                ]
            )
            plan = record.get("plan")
            if isinstance(plan, dict):
                lines.extend(
                    [
                        "### Plan",
                        "",
                        f"- summary: {plan.get('summary', '')}",
                        f"- strategy: {plan.get('strategy', '')}",
                        "",
                    ]
                )
                steps = plan.get("steps")
                if isinstance(steps, list):
                    for step in steps:
                        if isinstance(step, dict):
                            lines.append(f"- {step.get('id', '?')}: {step.get('description', '')}")
                    lines.append("")
            changed_files = record.get("changed_files")
            if changed_files:
                lines.extend(["### Changed Files", ""])
                lines.extend(f"- {path}" for path in changed_files)
                lines.append("")
            outcomes = record.get("outcomes")
            if isinstance(outcomes, list) and outcomes:
                lines.extend(["### Outcomes", ""])
                for outcome in outcomes:
                    if isinstance(outcome, dict):
                        lines.append(
                            f"- {outcome.get('status', '?')}: {outcome.get('summary', '')}"
                        )
                lines.append("")
            blockers = record.get("blockers")
            if isinstance(blockers, list) and blockers:
                lines.extend(["### Blockers", ""])
                lines.extend(f"- {blocker}" for blocker in blockers)
                lines.append("")
            diff = record.get("diff")
            if isinstance(diff, str) and diff:
                lines.extend(
                    [
                        "### Candidate Diff",
                        "",
                        _fenced(diff[:_MAX_HISTORY_DIFF_CHARS], "diff"),
                        "",
                    ]
                )
        lines.extend(
            [
                "## Retry Requirement",
                "",
                "Classify the LAST ATTEMPT, not the global best, as one of:",
                "1. continue: the last direction is still active; keep its effective changes and",
                " continue optimizing from its workspace.",
                "2. pivot: the last direction is exhausted; mark it exhausted and choose a",
                " materially different direction.",
                "3. rollback: the last attempt regressed or failed; return to its parent attempt",
                " and try a different substep in the same direction. If no substep remains, pivot.",
                "Global best is only a scoreboard and must not automatically become the parent.",
                "Set retryDecision.basedOnAttempt to the last attempt.",
                "Set retryDecision.parentAttempt to the workspace that should be used as the base.",
                "",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _write_text_atomic(path: Path, content: str) -> None:
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)

    @staticmethod
    def _append_index(scope_dir: Path, stem: str, record: dict[str, Any]) -> None:
        path = scope_dir / "index.md"
        if not path.exists():
            path.write_text(
                "# Optimization Records\n\n| Attempt | Command | Status | Improvement | File |\n"
                "| --- | --- | --- | --- | --- |\n",
                encoding="utf-8",
            )
        improvement = record.get("improvement_percent")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(
                f"| {record.get('attempt')} | {record.get('command', 'optimize')} | "
                f"{record.get('status', '')} | {improvement if improvement is not None else ''} | "
                f"[{stem}.json]({stem}.json) |\n"
            )


def _render_record_markdown(record: dict[str, Any]) -> str:
    lines = [
        f"# Optimization Record {record.get('attempt', '?')}",
        "",
        "## Metadata",
        "",
        f"- task_id: `{record.get('task_id', '')}`",
        f"- command: `{record.get('command', 'optimize')}`",
        f"- status: `{record.get('status', '')}`",
        f"- started_at: `{record.get('started_at', '')}`",
        f"- completed_at: `{record.get('completed_at', '')}`",
        f"- candidate_id: `{record.get('candidate_id', '')}`",
        f"- improvement_percent: `{record.get('improvement_percent', '')}`",
        "",
        "## Summary",
        "",
        str(record.get("summary", "")) or "(empty)",
        "",
    ]
    plan = record.get("plan")
    if plan is not None:
        lines.extend(
            [
                "## Optimization Plan",
                "",
                _fenced(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True), "json"),
                "",
            ]
        )
    diff = record.get("diff")
    if diff:
        lines.extend(["## Candidate Diff", "", _fenced(str(diff), "diff"), ""])
    benchmark = record.get("benchmark")
    if benchmark is not None:
        lines.extend(
            [
                "## Benchmark",
                "",
                _fenced(
                    json.dumps(benchmark, ensure_ascii=False, indent=2, sort_keys=True),
                    "json",
                ),
                "",
            ]
        )
    blockers = record.get("blockers")
    if blockers:
        lines.extend(["## Blockers", ""])
        lines.extend(f"- {blocker}" for blocker in blockers)
        lines.append("")
    error = record.get("error")
    if error is not None:
        lines.extend(["## Error", "", _fenced(str(error), "text"), ""])
    return "\n".join(lines).rstrip()


def _optional_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_command(value: Any) -> str:
    command = str(value or "optimize").strip().lower()
    return _SAFE_NAME.sub("-", command).strip("-") or "optimize"


def _fenced(content: str, language: str) -> str:
    fence = "```"
    while fence in content:
        fence += "`"
    return f"{fence}{language}\n{content}\n{fence}"
