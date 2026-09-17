"""Build application context for task-scoped CLI commands."""

from __future__ import annotations

import asyncio
from pathlib import Path

from algocode.application.services.project_state import find_current_task
from algocode.bootstrap import AppContext, build_context
from algocode.domain.model import Candidate, Task
from algocode.project_layout import ProjectLayout


def resolve_data_dir(
    data_dir: str | Path | None = None,
    *,
    start: str | Path | None = None,
) -> Path | None:
    """Resolve an explicit data directory or reuse the current project state."""

    if data_dir is not None:
        return Path(data_dir).expanduser()
    state = find_current_task(start or Path.cwd())
    if state is not None:
        configured = state.get("dataDir")
        if configured:
            return Path(str(configured)).expanduser()
        configured_root = state.get("root")
        if configured_root:
            return ProjectLayout.from_root(str(configured_root)).cache_dir
    current = Path(start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        layout = ProjectLayout.from_root(directory)
        if layout.algocode_dir.is_dir():
            return layout.cache_dir
    return None


def build_task_context(task_id: str, data_dir: str | Path | None = None) -> AppContext:
    """Resolve a task project and load project-level configuration."""

    resolved_data_dir = resolve_data_dir(data_dir)
    discovery = build_context(data_dir=resolved_data_dir)
    task = asyncio.run(discovery.task_service.get_task(task_id))
    project = asyncio.run(discovery.project_service.get(task.project_id))
    return build_context(project_root=project.root_path, data_dir=resolved_data_dir)


def resolve_current_task_id(task_id: str | None = None) -> str:
    """Resolve an explicit task id or the task stored in current-task.json."""

    if task_id:
        return task_id
    state = find_current_task(Path.cwd())
    if state is None or not state.get("taskId"):
        raise ValueError("no current task found; run algocode init or pass a task id")
    return str(state["taskId"])


def resolve_task_candidate(
    task_id: str | None = None,
    candidate_id: str | None = None,
    data_dir: str | Path | None = None,
) -> tuple[AppContext, Task, Candidate | None]:
    """Resolve a task and prefer the current or latest candidate."""

    resolved_task_id = resolve_current_task_id(task_id)
    context = build_task_context(resolved_task_id, data_dir)
    task = asyncio.run(context.task_service.get_task(resolved_task_id))
    if candidate_id is not None:
        return context, task, asyncio.run(context.candidate_service.get(candidate_id))
    state = find_current_task(Path.cwd())
    selected_id = None
    if state is not None and str(state.get("taskId")) == resolved_task_id:
        configured = state.get("candidateId")
        if configured:
            selected_id = str(configured)
    if selected_id is None and task.active_candidate_id is not None:
        selected_id = str(task.active_candidate_id)
    if selected_id is not None:
        try:
            return context, task, asyncio.run(context.candidate_service.get(selected_id))
        except Exception:
            pass
    candidates = asyncio.run(context.candidate_service.list_for_task(resolved_task_id))
    return context, task, candidates[0] if candidates else None
