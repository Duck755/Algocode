"""Read-only filesystem and task tools."""

from __future__ import annotations

from pathlib import Path

from algocode.domain.errors import NotFoundError
from algocode.languages.discovery import IGNORED_DIRECTORIES
from algocode.tools.types import ToolContext, ToolDefinition, ToolResult
from algocode.workspace import GitRepository

DEFAULT_MAX_RESULTS = 100
MAX_READ_BYTES = 200_000


async def list_files(context: ToolContext, arguments: dict[str, object]) -> ToolResult:
    pattern = str(arguments.get("pattern", "*"))
    max_results = _positive_int(arguments.get("max_results"), DEFAULT_MAX_RESULTS)
    matches: list[str] = []
    for path in sorted(context.workspace.rglob(pattern)):
        relative = path.relative_to(context.workspace)
        if any(part in IGNORED_DIRECTORIES for part in relative.parts):
            continue
        matches.append(relative.as_posix())
        if len(matches) >= max_results:
            break
    return ToolResult(
        status="success",
        summary=f"listed {len(matches)} paths",
        structured={"paths": matches},
        truncated=len(matches) >= max_results,
    )


async def read_file(context: ToolContext, arguments: dict[str, object]) -> ToolResult:
    relative_path = str(arguments.get("path", ""))
    target = _safe_path(context.workspace, relative_path)
    if not target.is_file():
        return ToolResult(status="error", summary=f"file not found: {relative_path}")
    raw = target.read_bytes()
    truncated = len(raw) > MAX_READ_BYTES
    content = raw[:MAX_READ_BYTES].decode(errors="replace")
    lines = content.splitlines()
    start_line = max(1, _positive_int(arguments.get("start_line"), 1))
    end_line = _positive_int(arguments.get("end_line"), len(lines))
    selected = lines[start_line - 1 : end_line]
    return ToolResult(
        status="success",
        summary=f"read {relative_path}",
        structured={
            "path": relative_path,
            "start_line": start_line,
            "end_line": min(end_line, len(lines)),
            "content": "\n".join(selected),
        },
        truncated=truncated,
    )


async def search_code(context: ToolContext, arguments: dict[str, object]) -> ToolResult:
    query = str(arguments.get("query", ""))
    if not query:
        return ToolResult(status="error", summary="query must not be empty")
    glob_pattern = str(arguments.get("glob", "*"))
    max_results = _positive_int(arguments.get("max_results"), DEFAULT_MAX_RESULTS)
    matches: list[dict[str, object]] = []
    for path in sorted(context.workspace.rglob(glob_pattern)):
        if not path.is_file():
            continue
        relative = path.relative_to(context.workspace)
        if any(part in IGNORED_DIRECTORIES for part in relative.parts):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(lines, start=1):
            if query in line:
                matches.append(
                    {
                        "path": relative.as_posix(),
                        "line": line_number,
                        "text": line[:500],
                    }
                )
                if len(matches) >= max_results:
                    break
        if len(matches) >= max_results:
            break
    return ToolResult(
        status="success",
        summary=f"found {len(matches)} matches",
        structured={"matches": matches},
        truncated=len(matches) >= max_results,
    )


async def read_resource(context: ToolContext, arguments: dict[str, object]) -> ToolResult:
    uri = str(arguments.get("uri", "")).strip()
    mode = str(arguments.get("mode", "summary"))
    if not uri:
        return ToolResult(status="error", summary="resource URI must not be empty")
    if context.resource_provider is None:
        return ToolResult(status="error", summary="resource provider is unavailable")
    try:
        resource = await context.resource_provider.resolve(
            uri,
            mode,
            workspace=context.workspace,
        )
    except (OSError, ValueError, NotFoundError) as exc:
        return ToolResult(status="error", summary=f"resource read failed: {exc}")
    return ToolResult(
        status="success",
        summary=resource.summary,
        structured=resource.payload(include_content=mode == "content"),
        truncated=bool(resource.metadata.get("truncated", False)),
    )


async def get_task_state(context: ToolContext, arguments: dict[str, object]) -> ToolResult:
    return ToolResult(
        status="success",
        summary=f"task {context.task.id} is in {context.phase.value}",
        structured={
            "task_id": str(context.task.id),
            "project_id": str(context.task.project_id),
            "objective": context.task.objective,
            "status": context.task.status.value,
            "phase": context.phase.value,
            "baseline_id": context.task.baseline_id,
            "candidate_id": context.candidate_id,
        },
    )


async def get_candidate_diff(context: ToolContext, arguments: dict[str, object]) -> ToolResult:
    repository = await GitRepository.discover(context.workspace)
    snapshot = await repository.capture_snapshot(context.workspace)
    untracked = [item.relative_path for item in snapshot.untracked]
    return ToolResult(
        status="success",
        summary=f"candidate diff contains {len(snapshot.patch)} bytes",
        structured={
            "patch": snapshot.patch.decode(errors="replace"),
            "untracked": untracked,
            "snapshot_hash": snapshot.snapshot_hash,
        },
    )


def register_read_tools(registry) -> None:
    registry.register(
        ToolDefinition(
            name="list_files",
            description="List files under the current workspace.",
            input_schema={
                "pattern": {"type": "string", "required": False},
                "max_results": {"type": "integer", "required": False},
            },
        ),
        list_files,
    )
    registry.register(
        ToolDefinition(
            name="read_file",
            description="Read a UTF-8 text file under the current workspace.",
            input_schema={
                "path": {"type": "string", "required": True},
                "start_line": {"type": "integer", "required": False},
                "end_line": {"type": "integer", "required": False},
            },
        ),
        read_file,
    )
    registry.register(
        ToolDefinition(
            name="search_code",
            description="Search text files under the current workspace.",
            input_schema={
                "query": {"type": "string", "required": True},
                "glob": {"type": "string", "required": False},
                "max_results": {"type": "integer", "required": False},
            },
        ),
        search_code,
    )
    registry.register(
        ToolDefinition(
            name="read_resource",
            description="Resolve a P0 resource URI in summary or content mode.",
            input_schema={
                "uri": {"type": "string", "required": True},
                "mode": {"type": "string", "required": False},
            },
        ),
        read_resource,
    )
    registry.register(
        ToolDefinition(
            name="get_task_state",
            description="Read the current task and phase state.",
            input_schema={},
        ),
        get_task_state,
    )
    registry.register(
        ToolDefinition(
            name="get_candidate_diff",
            description="Read the current candidate patch.",
            input_schema={},
        ),
        get_candidate_diff,
    )


def _safe_path(workspace: Path, relative_path: str) -> Path:
    root = workspace.resolve()
    target = (root / relative_path).resolve()
    if not target.is_relative_to(root):
        raise ValueError("path escapes the workspace")
    return target


def _positive_int(value: object, default: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        return default
    return max(1, parsed)
