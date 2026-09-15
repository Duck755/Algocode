"""Environment diagnostics for the Algocode CLI."""

from __future__ import annotations

import platform
import shutil
import sqlite3
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Annotated, Literal

import typer

from algocode import __version__
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.config.model import SandboxConfig
from algocode.sandbox.runner import SandboxProcessRunner
from algocode.storage.paths import default_data_dir

Status = Literal["ok", "warn", "error"]
DataDirOption = Annotated[
    Path | None,
    typer.Option("--data-dir", help="Override the data directory."),
]


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    name: str
    status: Status
    message: str


@dataclass(frozen=True, slots=True)
class DoctorReport:
    ok: bool
    version: str
    python: str
    platform: str
    data_dir: str
    checks: tuple[DoctorCheck, ...]


def _check_python() -> DoctorCheck:
    return DoctorCheck("python", "ok", platform.python_version())


def _check_git() -> DoctorCheck:
    path = shutil.which("git")
    if path:
        return DoctorCheck("git", "ok", path)
    return DoctorCheck("git", "error", "git executable not found on PATH")


def _check_sqlite() -> DoctorCheck:
    if sqlite3.sqlite_version_info >= (3, 35):
        return DoctorCheck("sqlite", "ok", sqlite3.sqlite_version)
    return DoctorCheck("sqlite", "error", "SQLite 3.35 or newer is required")


def _check_sandbox() -> DoctorCheck:
    runner = SandboxProcessRunner(SandboxConfig())
    if runner.backend == "disabled":
        return DoctorCheck(
            "sandbox",
            "error",
            "no Docker/WSL2 backend is available; execution tools will fail closed",
        )
    if runner.backend in {"docker", "wsl2"}:
        return DoctorCheck("sandbox", "ok", runner.backend)
    return DoctorCheck(
        "sandbox",
        "warn",
        "native restricted process only; Docker/WSL2 hard isolation unavailable",
    )


def _check_cpp_compiler() -> DoctorCheck:
    found = [name for name in ("g++", "clang++", "cl") if shutil.which(name)]
    if found:
        return DoctorCheck("cpp_compiler", "ok", ", ".join(found))
    return DoctorCheck(
        "cpp_compiler",
        "warn",
        "no C++ compiler found; Python-only tasks can still run",
    )


def _check_data_dir(data_dir: Path) -> DoctorCheck:
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=data_dir, prefix=".write-test-", delete=True):
            pass
    except OSError as exc:
        return DoctorCheck("data_dir", "error", f"{data_dir}: {exc}")
    return DoctorCheck("data_dir", "ok", str(data_dir))


def run_doctor(data_dir: Path | None = None) -> DoctorReport:
    """Run environment checks without modifying project repositories."""

    resolved_data_dir = data_dir or default_data_dir()
    checks = (
        _check_python(),
        _check_git(),
        _check_sqlite(),
        _check_sandbox(),
        _check_cpp_compiler(),
        _check_data_dir(resolved_data_dir),
    )
    return DoctorReport(
        ok=all(check.status != "error" for check in checks),
        version=__version__,
        python=platform.python_version(),
        platform=platform.platform(),
        data_dir=str(resolved_data_dir),
        checks=checks,
    )


def doctor_command(
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    report = run_doctor(data_dir)
    symbols = {"ok": "OK", "warn": "WARN", "error": "ERROR"}
    human_lines = (
        f"Algocode {report.version}",
        f"Python: {report.python}",
        f"Platform: {report.platform}",
        f"Data directory: {report.data_dir}",
        *(f"[{symbols[check.status]}] {check.name}: {check.message}" for check in report.checks),
    )
    emit_result(
        "doctor",
        data=asdict(report),
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        status="ok" if report.ok else "error",
        human_lines=human_lines,
    )
    if not report.ok:
        raise typer.Exit(code=1)
