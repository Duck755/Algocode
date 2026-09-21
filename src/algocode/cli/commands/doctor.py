"""Environment diagnostics for the Algocode CLI."""

from __future__ import annotations

import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Annotated, Literal

import typer

from algocode import __version__
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.config.model import SandboxConfig
from algocode.process_output import run_text
from algocode.sandbox.runner import SandboxProcessRunner, docker_tool_version, wsl_tool_version
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


@dataclass(frozen=True, slots=True)
class MissingDependency:
    key: str
    label: str
    detail: str


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


def _check_sandbox_and_tools(
    config: SandboxConfig,
) -> tuple[DoctorCheck, tuple[DoctorCheck, ...]]:
    if config.backend == "disabled":
        return (
            DoctorCheck(
                "sandbox",
                "error",
                "sandbox backend is disabled; execution tools will fail closed",
            ),
            (),
        )

    docker_runner = SandboxProcessRunner(config.model_copy(update={"backend": "docker"}))
    wsl_runner = SandboxProcessRunner(config.model_copy(update={"backend": "wsl2"}))
    docker_available = docker_runner.backend == "docker"
    wsl_available = wsl_runner.backend == "wsl2"
    available = [
        name for name, ready in (("docker", docker_available), ("wsl2", wsl_available)) if ready
    ]

    if available:
        sandbox_check = DoctorCheck("sandbox", "ok", " ".join(available))
    else:
        sandbox_check = DoctorCheck(
            "sandbox",
            "warn",
            "native restricted process only; Docker/WSL2 hard isolation unavailable",
        )

    tools: list[DoctorCheck] = []
    if docker_available:
        tools.append(
            _check_docker_tool(
                "g++",
                ("g++",),
                config.image,
                status="warn",
                missing_reason="C++ optimization in the docker sandbox will be unavailable",
            )
        )
        tools.append(
            _check_docker_tool(
                "python",
                ("python3", "python"),
                config.image,
                status="error",
                missing_reason="Python execution in the docker sandbox will fail",
            )
        )
    if wsl_available:
        tools.append(
            _check_wsl_tool(
                "g++",
                ("g++",),
                config.wsl_distro,
                status="warn",
                missing_reason="C++ optimization in the wsl2 sandbox will be unavailable",
            )
        )
        tools.append(
            _check_wsl_tool(
                "python",
                ("python3", "python"),
                config.wsl_distro,
                status="error",
                missing_reason="Python execution in the wsl2 sandbox will fail",
            )
        )
    return sandbox_check, tuple(tools)


def _check_wsl_tool(
    name: str,
    tools: tuple[str, ...],
    distro: str,
    *,
    status: Status,
    missing_reason: str,
) -> DoctorCheck:
    for tool in tools:
        version = wsl_tool_version(tool, distro)
        if version:
            return DoctorCheck(f"wsl {name}", "ok", version)
    return DoctorCheck(f"wsl {name}", status, f"not found in WSL {distro}; {missing_reason}")


def _check_docker_tool(
    name: str,
    tools: tuple[str, ...],
    image: str,
    *,
    status: Status,
    missing_reason: str,
) -> DoctorCheck:
    for tool in tools:
        version = docker_tool_version(tool, image)
        if version:
            return DoctorCheck(f"docker {name}", "ok", version)
    return DoctorCheck(
        f"docker {name}",
        status,
        f"not found in Docker image {image}; {missing_reason}",
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


_MISSING_CHECK_LABELS = {
    "python": ("python", "Python"),
    "cpp_compiler": ("cpp_compiler", "g++"),
    "git": ("git", "Git"),
    "sqlite": ("sqlite", "SQLite"),
    "docker g++": ("docker_g++", "Docker g++"),
    "docker python": ("docker_python", "Docker Python"),
    "wsl g++": ("wsl_g++", "WSL g++"),
    "wsl python": ("wsl_python", "WSL Python"),
}
_WINGET_MIN_VERSION = (1, 4)


def _missing_install_dependencies(report: DoctorReport) -> tuple[MissingDependency, ...]:
    dependencies = []
    for check in report.checks:
        label = _MISSING_CHECK_LABELS.get(check.name)
        if label is not None and check.status != "ok":
            dependencies.append(MissingDependency(label[0], label[1], check.message))
    return tuple(dependencies)


def _command_output(command: tuple[str, ...], *, timeout_seconds: int = 5) -> str:
    try:
        result = run_text(
            command,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _winget_version_at_least(executable: str) -> bool:
    output = _command_output((executable, "--version"))
    match = re.search(r"v?(\d+)\.(\d+)", output)
    if not match:
        return False
    return (int(match.group(1)), int(match.group(2))) >= _WINGET_MIN_VERSION


def _detect_package_manager() -> str | None:
    system = platform.system()
    if system == "Windows":
        winget = shutil.which("winget")
        if winget and _winget_version_at_least(winget):
            return "winget"
        if shutil.which("choco"):
            return "choco"
        return None
    if system == "Darwin":
        return "brew" if shutil.which("brew") else None
    if system == "Linux":
        for manager, executable in (
            ("apt", "apt-get"),
            ("dnf", "dnf"),
            ("yum", "yum"),
            ("pacman", "pacman"),
            ("apk", "apk"),
        ):
            if shutil.which(executable):
                return manager
    return None


def _host_install_command(key: str, manager: str | None) -> tuple[str, ...] | None:
    if key == "sqlite":
        return (sys.executable, "-m", "pip", "install", "pysqlite3")

    winget_packages = {
        "python": "Python.Python.3.13",
        "git": "Git.Git",
        "cpp_compiler": "BrechtSanders.WinLibs.POSIX.UCRT",
    }
    choco_packages = {"python": "python", "git": "git", "cpp_compiler": "mingw"}
    brew_packages = {"python": "python", "git": "git", "cpp_compiler": "gcc"}
    apt_packages = {"python": "python3", "git": "git", "cpp_compiler": "g++"}
    dnf_packages = {"python": "python3", "git": "git", "cpp_compiler": "gcc-c++"}
    yum_packages = dnf_packages
    pacman_packages = {"python": "python", "git": "git", "cpp_compiler": "gcc"}
    apk_packages = {"python": "python3", "git": "git", "cpp_compiler": "g++"}

    if manager == "winget":
        package = winget_packages.get(key)
        if package:
            return (
                "winget",
                "install",
                "--exact",
                "--id",
                package,
                "--source",
                "winget",
                "--accept-package-agreements",
                "--accept-source-agreements",
            )
    if manager == "choco":
        package = choco_packages.get(key)
        return ("choco", "install", package, "-y") if package else None
    if manager == "brew":
        package = brew_packages.get(key)
        return ("brew", "install", package) if package else None
    if manager == "apt":
        package = apt_packages.get(key)
        if package:
            return ("sh", "-lc", f"sudo apt-get update && sudo apt-get install -y {package}")
    if manager == "dnf":
        package = dnf_packages.get(key)
        if package:
            return ("sh", "-lc", f"sudo dnf install -y {package}")
    if manager == "yum":
        package = yum_packages.get(key)
        if package:
            return ("sh", "-lc", f"sudo yum install -y {package}")
    if manager == "pacman":
        package = pacman_packages.get(key)
        if package:
            return ("sh", "-lc", f"sudo pacman -S --noconfirm {package}")
    if manager == "apk":
        package = apk_packages.get(key)
        if package:
            return ("sh", "-lc", f"sudo apk add {package}")
    return None


def _wsl_install_command(key: str, distro: str) -> tuple[str, ...] | None:
    executable = shutil.which("wsl.exe") or shutil.which("wsl")
    if not executable:
        return None
    package = "g++" if key == "wsl_g++" else "python3"
    return (
        executable,
        "-d",
        distro,
        "-u",
        "root",
        "--",
        "bash",
        "-lc",
        f"apt-get update && apt-get install -y {package}",
    )


def _docker_install_hint(key: str, image: str) -> str:
    tool = "g++" if key == "docker_g++" else "python3"
    return (
        "Docker container tools cannot be installed persistently. "
        f"Rebuild or replace image {image} with {tool} included."
    )


def _install_missing_dependencies(
    dependencies: tuple[MissingDependency, ...],
    config: SandboxConfig,
) -> None:
    manager = _detect_package_manager()
    for dependency in dependencies:
        command: tuple[str, ...] | None = None
        hint: str | None = None
        if dependency.key.startswith("docker_"):
            hint = _docker_install_hint(dependency.key, config.image)
        elif dependency.key.startswith("wsl_"):
            command = _wsl_install_command(dependency.key, config.wsl_distro)
            hint = "WSL executable was not found" if command is None else None
        else:
            command = _host_install_command(dependency.key, manager)
            if command is None:
                hint = (
                    "No supported package manager was detected. "
                    "Install manually and run doctor again."
                )
            else:
                hint = None

        if command:
            print(f"Installing {dependency.label}: {' '.join(command)}")
            try:
                subprocess.run(command, check=False)
            except (OSError, subprocess.SubprocessError) as exc:
                print(f"Failed to install {dependency.label}: {exc}")
        else:
            print(f"Skipping {dependency.label}: {hint}")


def run_doctor(data_dir: Path | None = None) -> DoctorReport:
    """Run environment checks without modifying project repositories."""

    resolved_data_dir = data_dir or default_data_dir()
    sandbox_config = SandboxConfig()
    sandbox_check, sandbox_tools = _check_sandbox_and_tools(sandbox_config)
    checks = (
        _check_python(),
        _check_cpp_compiler(),
        _check_git(),
        _check_sqlite(),
        sandbox_check,
        *sandbox_tools,
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


def _emit_doctor_report(
    report: DoctorReport,
    *,
    json_output: bool,
    no_color: bool,
    quiet: bool,
    verbose: bool,
) -> None:
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


def doctor_command(
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    report = run_doctor(data_dir)
    _emit_doctor_report(
        report,
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
    )

    missing = _missing_install_dependencies(report)
    if missing and not json_output and not quiet and sys.stdin.isatty() and sys.stdout.isatty():
        print()
        print()
        print("Missing dependencies detected:")
        for dependency in missing:
            print(f"- {dependency.label}: {dependency.detail}")
        answer = input("Install missing dependencies now? [Y/N] ").strip().lower()
        if answer in {"y", "yes"}:
            _install_missing_dependencies(missing, SandboxConfig())
            print()
            print("Installation completed. Running doctor again:")
            report = run_doctor(data_dir)
            _emit_doctor_report(
                report,
                json_output=json_output,
                no_color=no_color,
                quiet=quiet,
                verbose=verbose,
            )
        else:
            print("Installation cancelled.")

    if not report.ok:
        raise typer.Exit(code=1)
