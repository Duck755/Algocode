"""Language profiler adapters."""

from __future__ import annotations

import os
import re
import shutil
import sys
import time
from pathlib import Path
from uuid import uuid4

from algocode.languages.discovery import iter_files
from algocode.profiling.types import ProfileReport, ProfileSample
from algocode.sandbox.runner import SandboxProcessRunner

_CPP_SUFFIXES = {".cpp", ".cc", ".cxx", ".c++"}
_PROFILE_LIMIT = 50


class PythonCProfileAdapter:
    """Collect Python hotspots with cProfile and pstats."""

    language = "python"
    tool = "cProfile"

    async def profile(
        self,
        workspace: Path,
        command: tuple[str, ...],
        *,
        timeout_seconds: int = 60,
        sandbox_runner: SandboxProcessRunner | None = None,
    ) -> ProfileReport:
        runner = sandbox_runner or SandboxProcessRunner()
        profile_dir = workspace / ".algocode" / "cache" / "profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        profile_path = profile_dir / f"python-{uuid4().hex}.prof"
        script_args = _python_script_args(command)
        if not script_args:
            return _unavailable("python", self.tool, command, 0.0, "no Python entrypoint was provided")
        started = time.perf_counter()
        try:
            result = await runner.run(
                (sys.executable, "-m", "cProfile", "-o", str(profile_path), *script_args),
                cwd=workspace,
                timeout_seconds=timeout_seconds,
                input_bytes=b"",
            )
        except (OSError, ValueError) as exc:
            return _unavailable(
                "python",
                self.tool,
                command,
                time.perf_counter() - started,
                str(exc),
            )
        duration = time.perf_counter() - started
        if result.start_failed or result.timed_out or result.exit_code != 0:
            return _unavailable(
                "python",
                self.tool,
                command,
                duration,
                result.stderr.decode(errors="replace").strip() or "profile run failed",
            )
        try:
            samples = _parse_pstats(profile_path)
        except (OSError, ValueError) as exc:
            return _unavailable("python", self.tool, command, duration, str(exc))
        finally:
            _remove_if_present(profile_path)
        if not samples:
            return _unavailable("python", self.tool, command, duration, "no profile samples found")
        return ProfileReport(
            language="python",
            tool=self.tool,
            available=True,
            command=command,
            duration_seconds=duration,
            samples=tuple(samples[: _PROFILE_LIMIT]),
        )


class CppGprofAdapter:
    """Collect C++ flat-profile hotspots with g++ -pg and gprof."""

    language = "cpp"
    tool = "gprof"

    async def profile(
        self,
        workspace: Path,
        command: tuple[str, ...],
        *,
        timeout_seconds: int = 60,
        sandbox_runner: SandboxProcessRunner | None = None,
    ) -> ProfileReport:
        runner = sandbox_runner or SandboxProcessRunner()
        compiler = shutil.which("g++") or shutil.which("clang++")
        gprof = shutil.which("gprof")
        if compiler is None or gprof is None:
            return _unavailable(
                "cpp",
                self.tool,
                command,
                0.0,
                "g++ and gprof are both required for C++ profiling",
            )
        sources = _cpp_sources(workspace)
        if not sources:
            return _unavailable("cpp", self.tool, command, 0.0, "no C++ source files found")
        source = next((path for path in sources if path.stem == "main"), sources[0])
        profile_dir = workspace / ".algocode" / "cache" / "profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        executable_name = "cpp-profile.exe" if os.name == "nt" else "cpp-profile"
        executable = profile_dir / executable_name
        gmon_path = workspace / "gmon.out"
        started = time.perf_counter()
        try:
            compile_result = await runner.run(
                (
                    compiler,
                    "-std=c++17",
                    "-O2",
                    "-pg",
                    "-pthread",
                    str(source),
                    "-o",
                    str(executable),
                ),
                cwd=workspace,
                timeout_seconds=timeout_seconds,
                input_bytes=b"",
            )
            if compile_result.start_failed or compile_result.timed_out or compile_result.exit_code != 0:
                return _unavailable(
                    "cpp",
                    self.tool,
                    command,
                    time.perf_counter() - started,
                    compile_result.stderr.decode(errors="replace").strip()
                    or "profile build failed",
                )
            run_result = await runner.run(
                (str(executable),),
                cwd=workspace,
                timeout_seconds=timeout_seconds,
                input_bytes=b"",
            )
            if run_result.start_failed or run_result.timed_out or run_result.exit_code != 0:
                return _unavailable(
                    "cpp",
                    self.tool,
                    command,
                    time.perf_counter() - started,
                    run_result.stderr.decode(errors="replace").strip()
                    or "profiled process failed",
                )
            gprof_result = await runner.run(
                (gprof, "-b", "-p", str(executable), str(gmon_path)),
                cwd=workspace,
                timeout_seconds=timeout_seconds,
                input_bytes=b"",
            )
        except (OSError, ValueError) as exc:
            return _unavailable("cpp", self.tool, command, time.perf_counter() - started, str(exc))
        finally:
            _remove_if_present(gmon_path)
        duration = time.perf_counter() - started
        if gprof_result.start_failed or gprof_result.timed_out or gprof_result.exit_code != 0:
            return _unavailable(
                "cpp",
                self.tool,
                command,
                duration,
                gprof_result.stderr.decode(errors="replace").strip() or "gprof failed",
            )
        samples = _parse_gprof(gprof_result.stdout)
        if not samples:
            return _unavailable("cpp", self.tool, command, duration, "no gprof samples found")
        return ProfileReport(
            language="cpp",
            tool=self.tool,
            available=True,
            command=command,
            duration_seconds=duration,
            samples=tuple(samples[: _PROFILE_LIMIT]),
        )


def _unavailable(
    language: str,
    tool: str,
    command: tuple[str, ...],
    duration: float,
    error: str,
) -> ProfileReport:
    return ProfileReport(
        language=language,
        tool=tool,
        available=False,
        command=command,
        duration_seconds=duration,
        error=error[:2000],
    )


def _python_script_args(command: tuple[str, ...]) -> tuple[str, ...]:
    if not command:
        return ()
    first = Path(command[0]).name.lower()
    if first in {"python", "python.exe", "python3", "python3.exe"}:
        return tuple(command[1:])
    return command


def _cpp_sources(workspace: Path) -> list[Path]:
    return sorted(
        path
        for path in iter_files(workspace)
        if path.is_file() and path.suffix.lower() in _CPP_SUFFIXES
    )


def _parse_pstats(path: Path) -> list[ProfileSample]:
    import pstats

    stats = pstats.Stats(str(path))
    samples: list[ProfileSample] = []
    for func, metrics in stats.stats.items():
        primitive_calls, total_calls, total_time, cumulative_time, _ = metrics
        filename, line, function = func
        samples.append(
            ProfileSample(
                function=function or filename or "<unknown>",
                file=filename or "",
                line=int(line) if line else 0,
                total_time=float(total_time),
                cumulative_time=float(cumulative_time),
                calls=int(total_calls or primitive_calls or 0),
            )
        )
    samples.sort(key=lambda sample: sample.cumulative_time, reverse=True)
    return samples


def _parse_gprof(stdout: bytes) -> list[ProfileSample]:
    text = stdout.decode(errors="replace")
    samples: list[ProfileSample] = []
    for line in text.splitlines():
        match = re.match(
            r"^\s*([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+(?:[0-9.]+)?\s*(.*)$",
            line,
        )
        if match is None:
            continue
        cumulative_time = float(match.group(2))
        total_time = float(match.group(3))
        name = match.group(4).strip()
        if not name or name.startswith(("%", "cumulative", "Flat profile")):
            continue
        samples.append(
            ProfileSample(
                function=name,
                file="",
                line=0,
                total_time=total_time,
                cumulative_time=cumulative_time,
                calls=0,
            )
        )
    samples.sort(key=lambda sample: sample.cumulative_time, reverse=True)
    return samples


def _remove_if_present(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
