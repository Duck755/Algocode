"""Build application context for task-scoped CLI commands."""

from __future__ import annotations

import asyncio
from pathlib import Path

from algocode.bootstrap import AppContext, build_context


def build_task_context(task_id: str, data_dir: str | Path | None = None) -> AppContext:
    """Resolve a task project and load project-level configuration."""

    discovery = build_context(data_dir=data_dir)
    task = asyncio.run(discovery.task_service.get_task(task_id))
    project = asyncio.run(discovery.project_service.get(task.project_id))
    return build_context(project_root=project.root_path, data_dir=data_dir)
