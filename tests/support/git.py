from __future__ import annotations

from pathlib import Path

from algocode.process_output import run_text


def init_git_repository(path: Path, files: dict[str, str] | None = None) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _run(path, "git", "init", "-q")
    _run(path, "git", "config", "user.email", "algocode@example.test")
    _run(path, "git", "config", "user.name", "Algocode Tests")
    for relative_path, content in (files or {}).items():
        target = path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    _run(path, "git", "add", ".")
    _run(path, "git", "commit", "-q", "-m", "initial")
    return path


def git_output(path: Path, *args: str) -> str:
    completed = run_text(
        ("git", *args),
        cwd=path,
        check=True,
        capture_output=True,
    )
    return completed.stdout.strip()


def _run(path: Path, *command: str) -> None:
    run_text(command, cwd=path, check=True, capture_output=True)
