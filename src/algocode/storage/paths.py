"""Platform-specific runtime directories."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from algocode.project_layout import ProjectLayout

APP_NAME = "algocode"


def project_data_dir(project_root: str | Path) -> Path:
    """Return the project-local state directory used by all project commands."""

    return ProjectLayout.from_root(project_root).cache_dir


def default_data_dir() -> Path:
    if sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA")
        return Path(root) / APP_NAME if root else Path.home() / "AppData" / "Local" / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    root = os.environ.get("XDG_DATA_HOME")
    return Path(root) / APP_NAME if root else Path.home() / ".local" / "share" / APP_NAME
