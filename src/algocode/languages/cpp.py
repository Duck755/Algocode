"""C++ language adapter."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from algocode.benchmark.engine import run_benchmark_process
from algocode.benchmark.spec import BenchmarkSpec
from algocode.benchmark.types import BenchmarkResult
from algocode.correctness.engine import run_process_correctness
from algocode.correctness.spec import CorrectnessSpec
from algocode.correctness.types import CorrectnessResult
from algocode.domain.model import Language
from algocode.languages.discovery import iter_files
from algocode.languages.runner import run_commands
from algocode.languages.types import (
    BuildProfile,
    BuildResult,
    Diagnostic,
    PrepareResult,
    ProjectInfo,
    resolve_source_root,
)

_CPP_SUFFIXES = {".cpp", ".cc", ".cxx", ".c++"}
_DIAGNOSTIC_PATTERN = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):(?:(?P<column>\d+):)? "
    r"(?P<severity>error|warning|note): (?P<message>.+)$"
)


class CppLanguageAdapter:
    """Detect, prepare, and build C++ projects."""

    language = Language.CPP

    def __init__(self, sandbox_runner=None) -> None:
        self._sandbox_runner = sandbox_runner

    async def detect(self, path: Path) -> ProjectInfo | None:
        root = path.resolve()
        sources = [
            candidate for candidate in iter_files(root) if candidate.suffix.lower() in _CPP_SUFFIXES
        ]
        has_project = (root / "CMakeLists.txt").exists() or (root / "Makefile").exists()
        if not sources and not has_project:
            return None
        if (root / "CMakeLists.txt").exists():
            build_system = "cmake"
        elif (root / "Makefile").exists():
            build_system = "make"
        else:
            build_system = "single-translation-unit"
        return ProjectInfo(root=root, languages=(Language.CPP,), build_system=build_system)

    async def prepare(self, workspace: Path, spec: object | None = None) -> PrepareResult:
        (workspace / "build").mkdir(parents=True, exist_ok=True)
        return PrepareResult(workspace=workspace.resolve())

    async def build(self, workspace: Path, spec: object) -> BuildResult:
        if not isinstance(spec, BuildProfile):
            raise TypeError("C++ build requires a BuildProfile")
        (workspace / "build").mkdir(parents=True, exist_ok=True)
        root = resolve_source_root(workspace, spec.source_root)
        commands = spec.commands or _default_commands(workspace, root)
        if not commands:
            return BuildResult(
                language=self.language,
                commands=(),
                exit_code=1,
                duration_seconds=0.0,
                stderr=b"no supported C++ build configuration was found",
            )
        results = await run_commands(
            commands,
            cwd=workspace,
            timeout_seconds=spec.timeout_seconds,
            sandbox_runner=self._sandbox_runner,
        )
        stderr = b"".join(result.stderr for result in results)
        executable_name = "algocode_baseline.exe" if os.name == "nt" else "algocode_baseline"
        executable = workspace / "build" / executable_name
        built_executable = executable if executable.exists() else None
        return BuildResult(
            language=self.language,
            commands=commands,
            exit_code=results[-1].exit_code if results else 1,
            duration_seconds=sum(result.duration_seconds for result in results),
            stdout=b"".join(result.stdout for result in results),
            stderr=stderr,
            diagnostics=_parse_diagnostics(stderr),
            executable=built_executable,
            run_command=(str(built_executable),) if built_executable else (),
        )

    async def run_correctness(self, workspace: Path, spec: object) -> CorrectnessResult:
        if not isinstance(spec, CorrectnessSpec):
            raise TypeError("C++ correctness requires a CorrectnessSpec")
        return await run_process_correctness(
            workspace,
            spec,
            sandbox_runner=self._sandbox_runner,
        )

    async def run_benchmark(self, workspace: Path, spec: object) -> BenchmarkResult:
        if not isinstance(spec, BenchmarkSpec):
            raise TypeError("C++ benchmark requires a BenchmarkSpec")
        return await run_benchmark_process(
            workspace,
            spec,
            target_kind="target",
            target_id="target",
            sandbox_runner=self._sandbox_runner,
        )


def _default_commands(workspace: Path, source_root: Path) -> tuple[tuple[str, ...], ...]:
    if (workspace / "CMakeLists.txt").exists():
        build_dir = workspace / "build"
        return (
            ("cmake", "-S", str(workspace), "-B", str(build_dir)),
            ("cmake", "--build", str(build_dir)),
        )
    if (workspace / "Makefile").exists():
        return (("make", "-C", str(workspace)),)
    sources = sorted(
        candidate
        for candidate in iter_files(source_root)
        if candidate.suffix.lower() in _CPP_SUFFIXES
    )
    if not sources:
        return ()
    compiler = shutil.which("g++") or shutil.which("clang++")
    if compiler is None:
        return ()
    source = next(
        (candidate for candidate in sources if candidate.stem == "main"),
        sources[0],
    )
    executable = "algocode_baseline.exe" if os.name == "nt" else "algocode_baseline"
    output = workspace / "build" / executable
    return ((compiler, "-std=c++17", "-O2", str(source), "-o", str(output)),)


def _parse_diagnostics(stderr: bytes) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for raw_line in stderr.decode(errors="replace").splitlines():
        match = _DIAGNOSTIC_PATTERN.match(raw_line)
        if match is None:
            continue
        diagnostics.append(
            Diagnostic(
                severity=match.group("severity"),
                message=match.group("message"),
                file=match.group("file"),
                line=int(match.group("line")),
                column=int(match.group("column")) if match.group("column") else None,
            )
        )
    return tuple(diagnostics)
