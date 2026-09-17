"""Markdown audit log for every model API call."""

from __future__ import annotations

import asyncio
import json
import re
import time
import traceback
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from algocode.providers.types import Message, ModelRequest, ModelResponse, ModelUsage
from algocode.security import SecretRedactor

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class ModelCallLogger:
    """Persist request, response, reasoning, tools, usage, and errors as Markdown."""

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
        task_id: str | None,
        phase: str,
        turn: int,
        request: ModelRequest,
        response: ModelResponse | None = None,
        duration_ms: int = 0,
        error: BaseException | None = None,
        traceback_text: str | None = None,
    ) -> Path:
        safe_scope = _SAFE_NAME.sub("_", scope_id).strip("._") or "model"
        scope_dir = self.root / safe_scope
        safe_phase = _SAFE_NAME.sub("_", phase).strip("._") or "phase"
        timestamp = datetime.now(UTC)
        async with self._lock:
            scope_dir.mkdir(parents=True, exist_ok=True)
            index = len(tuple(scope_dir.glob("[0-9][0-9][0-9][0-9]_*.md"))) + 1
            path = scope_dir / f"{index:04d}_{safe_phase}_turn_{turn:03d}.md"
            content = self._render(
                index=index,
                timestamp=timestamp,
                task_id=task_id,
                phase=phase,
                turn=turn,
                request=request,
                response=response,
                duration_ms=duration_ms,
                error=error,
                traceback_text=traceback_text,
            )
            await asyncio.to_thread(path.write_text, content, encoding="utf-8")
            await asyncio.to_thread(self._append_index, scope_dir, path.name, phase, turn)
            return path

    def _render(
        self,
        *,
        index: int,
        timestamp: datetime,
        task_id: str | None,
        phase: str,
        turn: int,
        request: ModelRequest,
        response: ModelResponse | None,
        duration_ms: int,
        error: BaseException | None,
        traceback_text: str | None,
    ) -> str:
        safe_request = self._redactor.redact_value(request)
        safe_response = self._redactor.redact_value(response) if response is not None else None
        metadata = safe_request.metadata
        stage = str(metadata.get("stage", ""))
        lines = [
            f"# Model Call {index:04d}",
            "",
            "## Metadata",
            "",
            f"- timestamp: `{timestamp.isoformat()}`",
            f"- task_id: `{task_id or ''}`",
            f"- phase: `{phase}`",
            f"- turn: `{turn}`",
            f"- stage: `{stage}`",
            f"- request_id: `{safe_request.request_id}`",
            f"- provider: `{safe_request.model.provider_id}`",
            f"- model: `{safe_request.model.model_id}`",
            f"- duration_ms: `{duration_ms}`",
            f"- context_hash: `{metadata.get('context_hash', '')}`",
            "",
            "## System Prompt",
            "",
            _fenced(safe_request.system or "(empty)", "text"),
            "",
            "## Input Messages",
            "",
            *_messages_markdown(safe_request.messages),
            "",
            "## Request Options",
            "",
            _fenced(
                json.dumps(
                    {
                        "tool_choice": safe_request.tool_choice,
                        "response_format": safe_request.response_format,
                        "generation": safe_request.generation,
                        "provider_options": safe_request.provider_options,
                        "timeout_seconds": safe_request.timeout_seconds,
                        "metadata": safe_request.metadata,
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ),
                "json",
            ),
            "",
            "## Tool Schemas",
            "",
            _fenced(
                json.dumps(safe_request.tools, ensure_ascii=False, indent=2, sort_keys=True),
                "json",
            ),
            "",
            "## Model Output",
            "",
        ]
        if error is not None:
            lines.extend(
                [
                    "### Error",
                    "",
                    f"- type: `{type(error).__name__}`",
                    f"- message: {error}",
                    "",
                    _fenced(traceback_text or "", "text"),
                    "",
                ]
            )
        if safe_response is not None:
            lines.extend(
                [
                    "### Text",
                    "",
                    _fenced(safe_response.text or "(empty)", "text"),
                    "",
                    "### Reasoning / Thinking",
                    "",
                    _fenced(
                        safe_response.reasoning or "(provider did not return reasoning content)",
                        "text",
                    ),
                    "",
                    "### Tool Calls",
                    "",
                    _fenced(_tool_calls_json(safe_response), "json"),
                    "",
                    "### Finish",
                    "",
                    f"- finish_reason: `{safe_response.finish_reason}`",
                    "",
                    "### Usage",
                    "",
                    _fenced(_usage_json(safe_response.usage), "json"),
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _append_index(scope_dir: Path, filename: str, phase: str, turn: int) -> None:
        path = scope_dir / "index.md"
        if not path.exists():
            path.write_text(
                "# Model Call Index\n\n| Call | Phase | Turn | File |\n| --- | --- | --- | --- |\n",
                encoding="utf-8",
            )
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"| {filename[:4]} | {phase} | {turn} | [{filename}]({filename}) |\n")


def _messages_markdown(messages: tuple[Message, ...]) -> list[str]:
    lines: list[str] = []
    if not messages:
        lines.extend(["(no messages)", ""])
        return lines
    for index, message in enumerate(messages, start=1):
        lines.extend([f"### Message {index}: {message.role}", ""])
        if message.tool_call_id is not None:
            lines.extend([f"- tool_call_id: `{message.tool_call_id}`", ""])
        if message.content:
            lines.extend([_fenced(message.content, "text"), ""])
        if message.reasoning_content:
            lines.extend(
                [
                    "Reasoning content:",
                    "",
                    _fenced(message.reasoning_content, "text"),
                    "",
                ]
            )
        if message.tool_calls:
            lines.extend(
                [
                    "Tool calls:",
                    "",
                    _fenced(
                        json.dumps(
                            [asdict(call) for call in message.tool_calls],
                            ensure_ascii=False,
                            indent=2,
                            sort_keys=True,
                        ),
                        "json",
                    ),
                    "",
                ]
            )
    return lines


def _tool_calls_json(response: ModelResponse) -> str:
    return json.dumps(
        [asdict(call) for call in response.tool_calls],
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _usage_json(usage: ModelUsage) -> str:
    return json.dumps(asdict(usage), ensure_ascii=False, indent=2, sort_keys=True)


def _fenced(content: str, language: str) -> str:
    fence = "```"
    while fence in content:
        fence += "`"
    return f"{fence}{language}\n{content}\n{fence}"


def model_call_duration_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def model_error_traceback() -> str:
    return traceback.format_exc()


def model_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return dict(metadata)
