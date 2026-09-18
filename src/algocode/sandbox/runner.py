"""Unified restricted subprocess execution."""

from __future__ import annotations

import asyncio
import os
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from algocode.config.model import SandboxConfig

DEFAULT_ALLOWED_ENV = (
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "TEMP",
    "TMP",
    "HOME",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
)


@dataclass(frozen=True, slots=True)
class SandboxProcessResult:
    command: tuple[str, ...]
    exit_code: int
    stdout: bytes
    stderr: bytes
    duration_seconds: float
    backend: str
    timed_out: bool = False
    start_failed: bool = False
    truncated: bool = False


class SandboxProcessRunner:
    """Run commands through Docker, WSL2, or a restricted native process."""

    def __init__(self, config: SandboxConfig | None = None) -> None:
        self.config = config or SandboxConfig(allowed_env=DEFAULT_ALLOWED_ENV)
        self.backend = self._select_backend()

    async def run(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path,
        timeout_seconds: int,
        input_bytes: bytes = b"",
        extra_env: dict[str, str] | None = None,
    ) -> SandboxProcessResult:
        started = time.perf_counter()
        environment = self._environment(extra_env)
        if self.backend == "disabled":
            return SandboxProcessResult(
                command=command,
                exit_code=126,
                stdout=b"",
                stderr=b"sandbox backend is disabled",
                duration_seconds=0.0,
                backend=self.backend,
                start_failed=True,
            )
        container_name: str | None = None
        if self.backend == "docker":
            actual_command, container_name = self._docker_command(
                command,
                cwd=cwd,
                environment=environment,
            )
        elif self.backend == "wsl2":
            actual_command = self._wsl_command(command, cwd=cwd, environment=environment)
        else:
            actual_command = command

        try:
            process = await asyncio.create_subprocess_exec(
                *actual_command,
                cwd=cwd if self.backend == "native" else None,
                env=environment if self.backend == "native" else None,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                preexec_fn=_posix_limits(self.config) if self.backend == "native" else None,
            )
        except (OSError, ValueError) as exc:
            return SandboxProcessResult(
                command=command,
                exit_code=127,
                stdout=b"",
                stderr=str(exc).encode(),
                duration_seconds=time.perf_counter() - started,
                backend=self.backend,
                start_failed=True,
            )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input_bytes),
                timeout=timeout_seconds,
            )
            exit_code = process.returncode if process.returncode is not None else 1
        except TimeoutError:
            await _terminate_process_tree(process)
            if container_name is not None:
                await _remove_container(container_name)
            stdout, stderr = await process.communicate()
            combined_stderr = stderr + b"\nprocess timed out"
            return SandboxProcessResult(
                command=command,
                exit_code=124,
                stdout=self._truncate(stdout),
                stderr=self._truncate(combined_stderr),
                duration_seconds=time.perf_counter() - started,
                backend=self.backend,
                timed_out=True,
                truncated=self._is_truncated(stdout) or self._is_truncated(combined_stderr),
            )
        truncated = self._is_truncated(stdout) or self._is_truncated(stderr)
        return SandboxProcessResult(
            command=command,
            exit_code=exit_code,
            stdout=self._truncate(stdout),
            stderr=self._truncate(stderr),
            duration_seconds=time.perf_counter() - started,
            backend=self.backend,
            truncated=truncated,
        )

    def _select_backend(self) -> str:
        if self.config.mode == "trusted-local":
            return "native"
        if self.config.backend == "disabled":
            return "disabled"
        if self.config.backend == "native":
            return "native"
        if self.config.backend == "docker":
            return "docker" if _docker_ready(self.config.image) else "disabled"
        if self.config.backend == "wsl2":
            return "wsl2" if _wsl_ready(self.config.wsl_distro, self.config.network) else "disabled"
        if _docker_ready(self.config.image):
            return "docker"
        if _wsl_ready(self.config.wsl_distro, self.config.network):
            return "wsl2"
        return "native"

    def _docker_command(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path,
        environment: dict[str, str],
    ) -> tuple[tuple[str, ...], str]:
        container_name = f"algocode-{uuid4().hex[:16]}"
        args = [
            "docker",
            "run",
            "--rm",
            "--interactive",
            "--name",
            container_name,
            "--network",
            "bridge" if self.config.network else "none",
            "--memory",
            f"{self.config.memory_mb}m",
            "--cpus",
            str(self.config.cpus),
            "--pids-limit",
            str(self.config.pids_limit),
        ]
        if self.config.read_only_root:
            args.extend(["--read-only", "--tmpfs", f"/tmp:rw,size={self.config.tmpfs_size_mb}m"])
        args.extend(
            [
                "--mount",
                f"type=bind,source={cwd.resolve()},target=/workspace",
                "--workdir",
                "/workspace",
            ]
        )
        container_environment = _container_environment(environment)
        for name, value in container_environment.items():
            args.extend(["--env", f"{name}={value}"])
        args.append(self.config.image)
        args.extend(_container_command(command, cwd.resolve()))
        return tuple(args), container_name

    def _wsl_command(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path,
        environment: dict[str, str],
    ) -> tuple[str, ...]:
        linux_cwd = _wsl_path(cwd)
        mapped = _container_command(command, cwd.resolve(), target=linux_cwd)
        container_environment = _container_environment(environment)
        env_prefix = " ".join(
            f"{shlex.quote(name)}={shlex.quote(value)}"
            for name, value in container_environment.items()
        )
        isolation = "" if self.config.network else "unshare -n -- "
        script = f"cd {shlex.quote(linux_cwd)} && {env_prefix} exec {isolation}{shlex.join(mapped)}"
        return (
            "wsl.exe",
            "-d",
            self.config.wsl_distro,
            "-u",
            "root",
            "--",
            "bash",
            "-lc",
            script,
        )

    def _environment(self, extra_env: dict[str, str] | None) -> dict[str, str]:
        allowed = {name.upper() for name in self.config.allowed_env}
        environment = {
            name: value
            for name, value in os.environ.items()
            if name.upper() in allowed and not _is_secret_name(name)
        }
        if extra_env:
            environment.update(
                {name: value for name, value in extra_env.items() if not _is_secret_name(name)}
            )
        environment["PYTHONHASHSEED"] = "0"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return environment

    def _truncate(self, data: bytes) -> bytes:
        return data[: self.config.max_output_bytes]

    def _is_truncated(self, data: bytes) -> bool:
        return len(data) > self.config.max_output_bytes


def _container_environment(environment: dict[str, str]) -> dict[str, str]:
    ignored = {
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "WINDIR",
        "TEMP",
        "TMP",
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
    }
    result = {
        name: value
        for name, value in environment.items()
        if name.upper() not in ignored and not _is_secret_name(name)
    }
    result.update(
        {
            "PATH": "/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin",
            "HOME": "/tmp",
            "TMPDIR": "/tmp",
            "PYTHONHASHSEED": "0",
        }
    )
    return result


def _container_command(
    command: tuple[str, ...],
    workspace: Path,
    *,
    target: str = "/workspace",
) -> tuple[str, ...]:
    return tuple(_map_argument(argument, workspace, target) for argument in command)


def _map_argument(argument: str, workspace: Path, target: str) -> str:
    mapped = argument.replace(str(workspace), target)
    if mapped.endswith("python.exe") or mapped.endswith("\\python.exe"):
        return "python3"
    basename = Path(mapped).name.lower()
    if basename.startswith(("g++", "clang++", "cl.exe")):
        return "g++" if basename.startswith("g++") else "clang++"
    return mapped.replace("\\", "/") if mapped.startswith(target) else mapped


def _wsl_path(path: Path) -> str:
    resolved = str(path.resolve())
    if len(resolved) >= 2 and resolved[1] == ":":
        drive = resolved[0].lower()
        remainder = resolved[2:].replace("\\", "/")
        return f"/mnt/{drive}{remainder}"
    return resolved.replace("\\", "/")


def _posix_limits(config: SandboxConfig):
    if os.name == "nt":
        return None

    def apply_limits() -> None:
        import resource

        memory_bytes = config.memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        resource.setrlimit(
            resource.RLIMIT_CPU,
            (config.timeout_seconds, config.timeout_seconds + 1),
        )
        resource.setrlimit(
            resource.RLIMIT_FSIZE,
            (config.max_output_bytes, config.max_output_bytes),
        )

    return apply_limits


async def _terminate_process_tree(process: asyncio.subprocess.Process) -> None:
    if os.name == "nt":
        await asyncio.create_subprocess_exec(
            "taskkill",
            "/F",
            "/T",
            "/PID",
            str(process.pid),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    else:
        process.kill()


async def _remove_container(container_name: str) -> None:
    await asyncio.create_subprocess_exec(
        "docker",
        "rm",
        "-f",
        container_name,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )


def _docker_ready(image: str) -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(
            ("docker", "image", "inspect", image),
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _wsl_ready(distro: str, network: bool) -> bool:
    if shutil.which("wsl.exe") is None and shutil.which("wsl") is None:
        return False
    executable = shutil.which("wsl.exe") or shutil.which("wsl")
    command = (
        (executable, "-d", distro, "-u", "root", "--", "unshare", "-n", "--", "true")
        if not network
        else (executable, "-d", distro, "--", "true")
    )
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _is_secret_name(name: str) -> bool:
    normalized = name.upper()
    return any(
        marker in normalized for marker in ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
    )
