"""Read-only filesystem and task tools."""

from __future__ import annotations

import hashlib
from pathlib import Path

from algocode.domain.errors import NotFoundError
from algocode.domain.model import TaskPhase
from algocode.languages.discovery import IGNORED_DIRECTORIES
from algocode.runtime.analysis import discover_required_files
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
        return ToolResult(
            status="error",
            summary=_unreadable_path_message(context.workspace, relative_path, target),
        )
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
            "path": target.relative_to(context.workspace.resolve()).as_posix(),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size": len(raw),
            "line_count": len(raw.decode(errors="replace").splitlines()),
            "start_line": start_line,
            "end_line": min(end_line, len(lines)),
            "content": "\n".join(selected),
        },
        truncated=truncated,
    )


async def read_required_files(context: ToolContext, arguments: dict[str, object]) -> ToolResult:
    files: list[dict[str, object]] = []
    total_bytes = 0
    for relative_path in discover_required_files(context.workspace):
        target = _safe_path(context.workspace, relative_path)
        try:
            raw = target.read_bytes()
        except OSError:
            continue
        if len(raw) > MAX_READ_BYTES:
            raw = raw[:MAX_READ_BYTES]
        total_bytes += len(raw)
        files.append(
            {
                "path": relative_path,
                "content": raw.decode(errors="replace"),
                "truncated": len(raw) >= MAX_READ_BYTES,
            }
        )
    return ToolResult(
        status="success",
        summary=f"read {len(files)} required files",
        structured={"files": files, "total_bytes": total_bytes},
        truncated=any(bool(item.get("truncated")) for item in files),
    )


async def write_file(context: ToolContext, arguments: dict[str, object]) -> ToolResult:
    error = _write_context_error(context)
    if error is not None:
        return error
    relative_path = str(arguments.get("path", ""))
    content = arguments.get("content")
    if not isinstance(content, str):
        return ToolResult(status="error", summary="content must be a string")
    try:
        target = _safe_path(context.workspace, relative_path)
    except ValueError as exc:
        return ToolResult(status="error", summary=str(exc))
    protected = _protected_path(relative_path, context.protected_files)
    if protected:
        return ToolResult(
            status="error",
            summary=f"write_file modifies protected file: {protected}",
        )

    expected_sha256 = arguments.get("expected_sha256")
    if target.exists():
        if not target.is_file():
            return ToolResult(status="error", summary=f"path is not a file: {relative_path}")
        if not isinstance(expected_sha256, str) or not expected_sha256:
            return ToolResult(
                status="error",
                summary="expected_sha256 is required when overwriting an existing file",
            )
        current_sha256 = hashlib.sha256(target.read_bytes()).hexdigest()
        if current_sha256 != expected_sha256:
            return ToolResult(
                status="error",
                summary="expected_sha256 does not match the current file",
                structured={
                    "path": relative_path,
                    "current_sha256": current_sha256,
                },
            )
    elif expected_sha256 not in {None, ""}:
        return ToolResult(
            status="error",
            summary="expected_sha256 was provided for a file that does not exist",
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(_normalize_text(content).encode("utf-8"))
    return await _mutation_result(context, relative_path, "wrote")


async def edit_file(context: ToolContext, arguments: dict[str, object]) -> ToolResult:
    error = _write_context_error(context)
    if error is not None:
        return error
    relative_path = str(arguments.get("path", ""))
    old_text = arguments.get("old_text")
    new_text = arguments.get("new_text")
    expected_sha256 = arguments.get("expected_sha256")
    if not isinstance(old_text, str) or not old_text:
        return ToolResult(status="error", summary="old_text must not be empty")
    if not isinstance(new_text, str):
        return ToolResult(status="error", summary="new_text must be a string")
    if not isinstance(expected_sha256, str) or not expected_sha256:
        return ToolResult(status="error", summary="expected_sha256 is required")
    try:
        target = _safe_path(context.workspace, relative_path)
    except ValueError as exc:
        return ToolResult(status="error", summary=str(exc))
    protected = _protected_path(relative_path, context.protected_files)
    if protected:
        return ToolResult(
            status="error",
            summary=f"edit_file modifies protected file: {protected}",
        )
    if not target.is_file():
        return ToolResult(status="error", summary=f"file not found: {relative_path}")

    raw = target.read_bytes()
    current_sha256 = hashlib.sha256(raw).hexdigest()
    if current_sha256 != expected_sha256:
        return ToolResult(
            status="error",
            summary="expected_sha256 does not match the current file",
            structured={"path": relative_path, "current_sha256": current_sha256},
        )
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        return ToolResult(status="error", summary="edit_file requires a UTF-8 text file")
    content = _normalize_text(content)
    old_text = _normalize_text(old_text)
    new_text = _normalize_text(new_text)
    occurrences = content.count(old_text)
    if occurrences != 1:
        return ToolResult(
            status="error",
            summary=f"old_text must occur exactly once; found {occurrences} occurrences",
        )
    target.write_bytes(content.replace(old_text, new_text, 1).encode("utf-8"))
    return await _mutation_result(context, relative_path, "edited")


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
            name="read_required_files",
            description=(
                "Read every Runtime-required analysis file in one call. Useful for completing "
                "ANALYZE coverage in two distinct turns."
            ),
            input_schema={},
        ),
        read_required_files,
    )
    registry.register(
        ToolDefinition(
            name="write_file",
            description=(
                "Create or replace a UTF-8 file in the candidate workspace. "
                "Overwriting an existing file requires its current sha256."
            ),
            input_schema={
                "path": {"type": "string", "required": True},
                "content": {"type": "string", "required": True},
                "expected_sha256": {"type": "string", "required": False},
            },
            effects="write",
            idempotent=False,
            parallelizable=False,
        ),
        write_file,
    )
    registry.register(
        ToolDefinition(
            name="edit_file",
            description=(
                "Replace one uniquely matching text region in a candidate file. "
                "Requires the file's current sha256."
            ),
            input_schema={
                "path": {"type": "string", "required": True},
                "old_text": {"type": "string", "required": True},
                "new_text": {"type": "string", "required": True},
                "expected_sha256": {"type": "string", "required": True},
            },
            effects="write",
            idempotent=False,
            parallelizable=False,
        ),
        edit_file,
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


def _write_context_error(context: ToolContext) -> ToolResult | None:
    if context.phase is not TaskPhase.IMPLEMENT:
        return ToolResult(
            status="error",
            summary="file modification tools are only allowed in implement",
        )
    if context.candidate_id is None:
        return ToolResult(
            status="error",
            summary="file modification tools require an active candidate",
        )
    return None


def _protected_path(relative_path: str, patterns: tuple[str, ...]) -> str | None:
    normalized = relative_path.replace("\\", "/").lstrip("./")
    for pattern in patterns:
        prefix = pattern.replace("\\", "/").rstrip("/")
        if normalized == prefix or normalized.startswith(f"{prefix}/"):
            return normalized
    return None


def _normalize_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


async def _mutation_result(
    context: ToolContext,
    relative_path: str,
    action: str,
) -> ToolResult:
    repository = await GitRepository.discover(context.workspace)
    snapshot = await repository.capture_snapshot(context.workspace)
    changed_files = await repository.changed_files(context.workspace)
    return ToolResult(
        status="success",
        summary=f"{action} {relative_path}",
        structured={
            "applied_files": [relative_path],
            "changed_files": list(changed_files),
            "patch_hash": snapshot.snapshot_hash,
            "snapshot_hash": snapshot.snapshot_hash,
        },
    )


def _safe_path(workspace: Path, relative_path: str) -> Path:
    root = workspace.resolve()
    target = (root / relative_path).resolve()
    if not target.is_relative_to(root):
        raise ValueError("path escapes the workspace")
    return target


def _directory_entries(directory: Path, limit: int = 25) -> str:
    try:
        names = sorted(
            f"{entry.name}/" if entry.is_dir() else entry.name
            for entry in directory.iterdir()
            if entry.name not in IGNORED_DIRECTORIES
        )
    except OSError:
        return "(unreadable)"
    if not names:
        return "(empty)"
    extra = len(names) - limit
    suffix = f" ... (+{extra} more)" if extra > 0 else ""
    return ", ".join(names[:limit]) + suffix


def _unreadable_path_message(workspace: Path, relative_path: str, target: Path) -> str:
    """Explain an unreadable path so the next attempt can succeed."""

    if target.is_dir():
        return (
            f"{relative_path} is a directory, not a file; use list_files to explore it. "
            f"It contains: {_directory_entries(target)}"
        )
    parent = target.parent
    if parent.is_dir():
        shown = parent.relative_to(workspace.resolve()).as_posix() or "."
        return (
            f"file not found: {relative_path}; {shown} contains: "
            f"{_directory_entries(parent)}"
        )
    return f"file not found: {relative_path}; use list_files to see which paths exist"


def _positive_int(value: object, default: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        return default
    return max(1, parsed)
