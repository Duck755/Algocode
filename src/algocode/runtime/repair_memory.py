"""Durable repair memory and prompt context for failed candidate checks."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from algocode.security import SecretRedactor

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_DIFF_CHARS = 20_000


@dataclass(slots=True)
class RepairAttempt:
    attempt: int
    timestamp: str
    phase: str
    candidate_id: str
    tool_name: str
    failure: dict[str, Any]
    snapshot_hash: str
    changed_files: tuple[str, ...] = ()
    diff: str = ""
    required_action: str = "patch the candidate, then run run_candidate_check again"


@dataclass(slots=True)
class RepairMemory:
    scope_id: str
    attempts: list[RepairAttempt] = field(default_factory=list)


class RepairMemoryStore:
    """Persist repair attempts and render a focused repair-context fragment."""

    def __init__(
        self,
        root: str | Path,
        *,
        redactor: SecretRedactor | None = None,
    ) -> None:
        self.root = Path(root).expanduser()
        self._redactor = redactor or SecretRedactor()
        self._lock = asyncio.Lock()

    async def record(
        self,
        *,
        scope_id: str,
        phase: str,
        candidate_id: str,
        tool_name: str,
        failure: dict[str, Any],
        snapshot_hash: str,
        changed_files: tuple[str, ...],
        diff: str,
    ) -> RepairMemory:
        safe_scope = _SAFE_NAME.sub("_", scope_id).strip("._") or "unknown"
        scope_dir = self.root / safe_scope
        async with self._lock:
            memory = await asyncio.to_thread(self._load_sync, scope_dir, scope_id)
            attempt = RepairAttempt(
                attempt=len(memory.attempts) + 1,
                timestamp=datetime.now(UTC).isoformat(),
                phase=phase,
                candidate_id=candidate_id,
                tool_name=tool_name,
                failure=self._redactor.redact_value(failure),
                snapshot_hash=snapshot_hash,
                changed_files=changed_files,
                diff=self._redactor.redact_text(diff[:_MAX_DIFF_CHARS]),
            )
            memory.attempts.append(attempt)
            await asyncio.to_thread(self._write_sync, scope_dir, memory)
            return memory

    def load(self, *, scope_id: str) -> RepairMemory:
        safe_scope = _SAFE_NAME.sub("_", scope_id).strip("._") or "unknown"
        return self._load_sync(self.root / safe_scope, scope_id)

    def render_brief(
        self,
        *,
        memory: RepairMemory,
        plan_step: str = "",
    ) -> str:
        if not memory.attempts:
            return ""
        latest = memory.attempts[-1]
        lines = [
            "# Candidate Repair Context",
            "",
            f"- attempt: {latest.attempt}",
            f"- phase: {latest.phase}",
            f"- candidate_id: {latest.candidate_id}",
            f"- failed_tool: {latest.tool_name}",
            f"- snapshot_hash: {latest.snapshot_hash}",
        ]
        if plan_step:
            lines.append(f"- current_plan_step: {plan_step}")
        lines.extend(
            [
                "",
                "## Failure Evidence",
                "",
                _fenced(
                    json.dumps(latest.failure, ensure_ascii=False, indent=2, sort_keys=True),
                    "json",
                ),
                "",
                "## Changed Files",
                "",
                *(f"- {path}" for path in latest.changed_files),
                "",
                "## Current Candidate Diff",
                "",
                _fenced(latest.diff or "(no tracked diff)", "diff"),
                "",
                "## Previous Repair Attempts",
                "",
            ]
        )
        for attempt in memory.attempts[:-1]:
            lines.append(
                f"- attempt {attempt.attempt}: {attempt.tool_name} failed; "
                f"snapshot={attempt.snapshot_hash}; files={list(attempt.changed_files)}"
            )
        if len(memory.attempts) == 1:
            lines.append("- none")
        lines.extend(
            [
                "",
                "## Required Next Action",
                "",
                "Patch the candidate now using apply_patch, edit_file, or write_file.",
                "Do not submit the phase and do not repeat the same read-only inspection loop.",
                "After patching, run run_candidate_check again.",
                "",
            ]
        )
        return "\n".join(lines)

    def _load_sync(self, scope_dir: Path, scope_id: str) -> RepairMemory:
        path = scope_dir / "attempts.json"
        if not path.is_file():
            return RepairMemory(scope_id=scope_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return RepairMemory(scope_id=scope_id)
        attempts: list[RepairAttempt] = []
        for item in payload.get("attempts", []):
            if not isinstance(item, dict):
                continue
            attempts.append(
                RepairAttempt(
                    attempt=int(item.get("attempt", len(attempts) + 1)),
                    timestamp=str(item.get("timestamp", "")),
                    phase=str(item.get("phase", "")),
                    candidate_id=str(item.get("candidate_id", "")),
                    tool_name=str(item.get("tool_name", "")),
                    failure=item.get("failure") if isinstance(item.get("failure"), dict) else {},
                    snapshot_hash=str(item.get("snapshot_hash", "")),
                    changed_files=tuple(str(value) for value in item.get("changed_files", [])),
                    diff=str(item.get("diff", "")),
                    required_action=str(item.get("required_action", "")),
                )
            )
        return RepairMemory(scope_id=scope_id, attempts=attempts)

    def _write_sync(self, scope_dir: Path, memory: RepairMemory) -> None:
        scope_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "scope_id": memory.scope_id,
            "attempts": [asdict(attempt) for attempt in memory.attempts],
        }
        canonical = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        (scope_dir / "attempts.json").write_text(canonical, encoding="utf-8")
        (scope_dir / "memory.md").write_text(
            self.render_brief(memory=memory) + "\n",
            encoding="utf-8",
        )


def _fenced(content: str, language: str) -> str:
    fence = "```"
    while fence in content:
        fence += "`"
    return f"{fence}{language}\n{content}\n{fence}"
