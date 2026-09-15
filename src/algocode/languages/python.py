"""Python language adapter."""

from __future__ import annotations

import sys
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
    PrepareResult,
    ProjectInfo,
    resolve_source_root,
)


class PythonLanguageAdapter:
    """Detect, prepare, and build Python projects."""

    language = Language.PYTHON

    def __init__(self, sandbox_runner=None) -> None:
        self._sandbox_runner = sandbox_runner

    async def detect(self, path: Path) -> ProjectInfo | None:
        root = path.resolve()
        has_python = any(candidate.suffix == ".py" for candidate in iter_files(root))
        has_project = (root / "pyproject.toml").exists() or (root / "setup.py").exists()
        if not has_python and not has_project:
            return None
        build_system = "pyproject" if (root / "pyproject.toml").exists() else "plain-python"
        return ProjectInfo(root=root, languages=(Language.PYTHON,), build_system=build_system)

    async def prepare(self, workspace: Path, spec: object | None = None) -> PrepareResult:
        return PrepareResult(workspace=workspace.resolve())

    async def build(self, workspace: Path, spec: object) -> BuildResult:
        if not isinstance(spec, BuildProfile):
            raise TypeError("Python build requires a BuildProfile")
        commands = spec.commands or (
            (
                sys.executable,
                "-m",
                "compileall",
                "-q",
                str(resolve_source_root(workspace, spec.source_root)),
            ),
        )
        results = await run_commands(
            commands,
            cwd=workspace,
            timeout_seconds=spec.timeout_seconds,
            sandbox_runner=self._sandbox_runner,
        )
        main_path = workspace / "main.py"
        run_command = (sys.executable, str(main_path)) if main_path.exists() else ()
        return BuildResult(
            language=self.language,
            commands=commands,
            exit_code=results[-1].exit_code if results else 1,
            duration_seconds=sum(result.duration_seconds for result in results),
            stdout=b"".join(result.stdout for result in results),
            stderr=b"".join(result.stderr for result in results),
            run_command=run_command,
        )

    async def run_correctness(self, workspace: Path, spec: object) -> CorrectnessResult:
        if not isinstance(spec, CorrectnessSpec):
            raise TypeError("Python correctness requires a CorrectnessSpec")
        return await run_process_correctness(
            workspace,
            spec,
            sandbox_runner=self._sandbox_runner,
        )

    async def run_benchmark(self, workspace: Path, spec: object) -> BenchmarkResult:
        if not isinstance(spec, BenchmarkSpec):
            raise TypeError("Python benchmark requires a BenchmarkSpec")
        return await run_benchmark_process(
            workspace,
            spec,
            target_kind="target",
            target_id="target",
            sandbox_runner=self._sandbox_runner,
        )
