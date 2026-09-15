"""C++ and Python language adapter port."""

from pathlib import Path
from typing import Protocol

from algocode.benchmark.spec import BenchmarkSpec
from algocode.benchmark.types import BenchmarkResult
from algocode.correctness.spec import CorrectnessSpec
from algocode.correctness.types import CorrectnessResult
from algocode.languages.types import BuildProfile, BuildResult, PrepareResult, ProjectInfo


class LanguageAdapter(Protocol):
    async def detect(self, path: Path) -> ProjectInfo | None: ...

    async def prepare(self, workspace: Path, spec: BuildProfile | None) -> PrepareResult: ...

    async def build(self, workspace: Path, spec: BuildProfile) -> BuildResult: ...

    async def run_correctness(
        self,
        workspace: Path,
        spec: CorrectnessSpec,
    ) -> CorrectnessResult: ...

    async def run_benchmark(
        self,
        workspace: Path,
        spec: BenchmarkSpec,
    ) -> BenchmarkResult: ...
