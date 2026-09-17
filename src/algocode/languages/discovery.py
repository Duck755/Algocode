"""Source-file discovery shared by language adapters."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

IGNORED_DIRECTORIES = {
    ".algocode",
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}


def iter_files(root: Path) -> Iterator[Path]:
    for directory, directory_names, file_names in os.walk(root):
        directory_names[:] = [name for name in directory_names if name not in IGNORED_DIRECTORIES]
        for file_name in file_names:
            yield Path(directory) / file_name
