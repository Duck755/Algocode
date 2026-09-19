"""Unified restricted subprocess execution."""

from __future__ import annotations

import asyncio
import ctypes
import os
import shlex
import shutil
import subprocess
import sys
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
TIME_OUTPUT_FORMAT = "user=%U sys=%S maxrss=%M major_faults=%F minor_faults=%R"


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
    cpu_time_seconds: float | None = None
    peak_memory_bytes: int | None = None
    page_faults: int | None = None


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
        measure_resources: bool = False,
    ) -> SandboxProcessResult:
        started = time.perf_counter()
        environment = self._environment(extra_env)
        posix_before = (
            _posix_child_usage()
            if self.backend == "native" and os.name != "nt" and measure_resources
            else None
        )
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
        time_output_name = f".algocode-time-{uuid4().hex}"
        time_output_host: Path | None = None
        if self.backend == "docker":
            actual_command, container_name = self._docker_command(
                command,
                cwd=cwd,
                environment=environment,
                time_output_path=(
                    f"/workspace/{time_output_name}" if measure_resources else None
                ),
            )
            if measure_resources:
                time_output_host = cwd.resolve() / time_output_name
        elif self.backend == "wsl2":
            actual_command = self._wsl_command(
                command,
                cwd=cwd,
                environment=environment,
                time_output_path=(
                    f"{_wsl_path(cwd)}/{time_output_name}" if measure_resources else None
                ),
            )
            if measure_resources:
                time_output_host = cwd.resolve() / time_output_name
        else:
            actual_command = command

        resource_monitor: asyncio.Task | None = None
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
            if self.backend == "native" and os.name == "nt" and measure_resources:
                resource_monitor = asyncio.create_task(_monitor_windows_process(process.pid))
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
            resources = await _finish_resources(
                resource_monitor,
                posix_before,
                time_output_host,
            )
            return SandboxProcessResult(
                command=command,
                exit_code=124,
                stdout=self._truncate(stdout),
                stderr=self._truncate(combined_stderr),
                duration_seconds=time.perf_counter() - started,
                backend=self.backend,
                timed_out=True,
                truncated=self._is_truncated(stdout) or self._is_truncated(combined_stderr),
                cpu_time_seconds=resources[0],
                peak_memory_bytes=resources[1],
                page_faults=resources[2],
            )
        resources = await _finish_resources(
            resource_monitor,
            posix_before,
            time_output_host,
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
            cpu_time_seconds=resources[0],
            peak_memory_bytes=resources[1],
            page_faults=resources[2],
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
        time_output_path: str | None = None,
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
        container_command = _container_command(command, cwd.resolve())
        if time_output_path is not None:
            container_command = (
                "/usr/bin/time",
                "-o",
                time_output_path,
                "-f",
                TIME_OUTPUT_FORMAT,
                "--",
                *container_command,
            )
        args.extend(container_command)
        return tuple(args), container_name

    def _wsl_command(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path,
        environment: dict[str, str],
        time_output_path: str | None = None,
    ) -> tuple[str, ...]:
        linux_cwd = _wsl_path(cwd)
        mapped = _container_command(command, cwd.resolve(), target=linux_cwd)
        container_environment = _container_environment(environment)
        env_prefix = " ".join(
            f"{shlex.quote(name)}={shlex.quote(value)}"
            for name, value in container_environment.items()
        )
        isolation = "" if self.config.network else "unshare -n -- "
        time_prefix = ""
        if time_output_path is not None:
            time_prefix = (
                f"/usr/bin/time -o {shlex.quote(time_output_path)} "
                f"-f {shlex.quote(TIME_OUTPUT_FORMAT)} -- "
            )
        script = (
            f"cd {shlex.quote(linux_cwd)} && {env_prefix} exec "
            f"{isolation}{time_prefix}{shlex.join(mapped)}"
        )
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


async def _finish_resources(
    monitor: asyncio.Task | None,
    posix_before,
    time_output_host: Path | None,
) -> tuple[float | None, int | None, int | None]:
    if monitor is not None:
        return await monitor
    if posix_before is not None:
        return _posix_child_delta(posix_before)
    if time_output_host is not None:
        try:
            return _parse_time_output(time_output_host.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None, None, None
        finally:
            _remove_if_present(time_output_host)
    return None, None, None


def _posix_child_usage():
    import resource

    return resource.getrusage(resource.RUSAGE_CHILDREN)


def _posix_child_delta(before) -> tuple[float | None, int | None, int | None]:
    import resource

    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu_time = (after.ru_utime + after.ru_stime) - (before.ru_utime + before.ru_stime)
    page_faults = (after.ru_minflt + after.ru_majflt) - (
        before.ru_minflt + before.ru_majflt
    )
    peak_memory = int(after.ru_maxrss)
    if sys.platform == "linux":
        peak_memory *= 1024
    return (
        cpu_time if cpu_time >= 0 else None,
        peak_memory if peak_memory > 0 else None,
        page_faults if page_faults >= 0 else None,
    )


def _parse_time_output(data: str) -> tuple[float | None, int | None, int | None]:
    fields: dict[str, float] = {}
    for token in data.split():
        if "=" not in token:
            continue
        name, value = token.split("=", 1)
        try:
            fields[name] = float(value)
        except ValueError:
            continue
    user = fields.get("user")
    system = fields.get("sys")
    cpu_time = (user + system) if user is not None and system is not None else None
    maxrss = fields.get("maxrss")
    peak_memory = int(maxrss * 1024) if maxrss is not None and maxrss > 0 else None
    major = fields.get("major_faults", 0.0)
    minor = fields.get("minor_faults", 0.0)
    page_faults = int(major + minor)
    return cpu_time, peak_memory, page_faults if page_faults > 0 else None


def _remove_if_present(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


async def _monitor_windows_process(pid: int) -> tuple[float | None, int | None, int | None]:
    """Best-effort CPU, peak working-set, and page-fault accounting for native Windows."""

    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    process_query_limited_information = 0x1000
    process_query_information = 0x0400
    process_vm_read = 0x0010
    still_active = 259

    class FileTime(ctypes.Structure):
        _fields_ = [
            ("dwLowDateTime", ctypes.c_ulong),
            ("dwHighDateTime", ctypes.c_ulong),
        ]

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    access = (
        process_query_limited_information | process_query_information | process_vm_read
    )
    handle = kernel32.OpenProcess(access, False, pid)
    if not handle:
        return None, None, None
    try:
        peak_memory = 0
        page_faults = 0
        while True:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                break
            if exit_code.value != still_active:
                break
            counters = ProcessMemoryCounters()
            counters.cb = ctypes.sizeof(ProcessMemoryCounters)
            if psapi.GetProcessMemoryInfo(
                handle,
                ctypes.byref(counters),
                ctypes.sizeof(ProcessMemoryCounters),
            ):
                peak_memory = max(peak_memory, int(counters.PeakWorkingSetSize))
                page_faults = int(counters.PageFaultCount)
            await asyncio.sleep(0.02)

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(ProcessMemoryCounters)
        if psapi.GetProcessMemoryInfo(
            handle,
            ctypes.byref(counters),
            ctypes.sizeof(ProcessMemoryCounters),
        ):
            peak_memory = max(peak_memory, int(counters.PeakWorkingSetSize))
            page_faults = int(counters.PageFaultCount)

        creation = FileTime()
        exit = FileTime()
        kernel = FileTime()
        user = FileTime()
        cpu_time = None
        if kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            def _hundreds_of_nanoseconds(value: FileTime) -> int:
                return (value.dwHighDateTime << 32) | value.dwLowDateTime

            cpu_time = (
                _hundreds_of_nanoseconds(kernel) + _hundreds_of_nanoseconds(user)
            ) / 10_000_000.0
        return (
            cpu_time,
            peak_memory if peak_memory > 0 else None,
            page_faults if page_faults > 0 else None,
        )
    finally:
        kernel32.CloseHandle(handle)


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
