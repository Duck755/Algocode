"""Canonical and legacy project layout paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProjectLayout:
    root: Path

    @classmethod
    def from_root(cls, root: str | Path) -> ProjectLayout:
        return cls(Path(root).expanduser().resolve())

    @property
    def algocode_dir(self) -> Path:
        return self.root / ".algocode"

    @property
    def config_path(self) -> Path:
        return self.algocode_dir / "config.yaml"

    @property
    def legacy_config_path(self) -> Path:
        return self.root / ".algocode.yaml"

    @property
    def local_config_path(self) -> Path:
        return self.algocode_dir / "config.local.yaml"

    @property
    def legacy_local_config_path(self) -> Path:
        return self.root / ".algocode.local.yaml"

    @property
    def oracle_dir(self) -> Path:
        return self.algocode_dir / "oracle"

    @property
    def reference_dir(self) -> Path:
        return self.oracle_dir / "reference"

    @property
    def legacy_oracle_dir(self) -> Path:
        return self.root / "oracle"

    @property
    def benchmarks_dir(self) -> Path:
        return self.algocode_dir / "benchmarks"

    @property
    def legacy_benchmarks_dir(self) -> Path:
        return self.root / "benchmarks"

    @property
    def contract_path(self) -> Path:
        return self.algocode_dir / "contract.json"

    @property
    def correctness_spec_path(self) -> Path:
        return self.oracle_dir / "correctness.yaml"

    @property
    def legacy_correctness_spec_path(self) -> Path:
        return self.legacy_oracle_dir / "correctness.yaml"

    @property
    def benchmark_spec_path(self) -> Path:
        return self.benchmarks_dir / "benchmark.yaml"

    @property
    def legacy_benchmark_spec_path(self) -> Path:
        return self.legacy_benchmarks_dir / "benchmark.yaml"

    @property
    def contract_test_path(self) -> Path:
        return self.oracle_dir / "contract_test.py"

    @property
    def cpp_contract_test_path(self) -> Path:
        return self.oracle_dir / "contract_test.cpp"

    @property
    def legacy_contract_test_path(self) -> Path:
        return self.legacy_oracle_dir / "contract_test.py"

    @property
    def task_summary_path(self) -> Path:
        return self.algocode_dir / "task.txt"

    @property
    def current_task_path(self) -> Path:
        return self.algocode_dir / "current-task.json"

    @property
    def cache_dir(self) -> Path:
        return self.algocode_dir / "cache"

    @property
    def records_dir(self) -> Path:
        return self.cache_dir / "optimization-records"

    def config_candidates(self) -> tuple[Path, ...]:
        return (self.config_path, self.legacy_config_path)

    def correctness_spec(self) -> Path:
        return _prefer_existing(self.correctness_spec_path, self.legacy_correctness_spec_path)

    def benchmark_spec(self) -> Path:
        return _prefer_existing(self.benchmark_spec_path, self.legacy_benchmark_spec_path)

    def contract_test(self) -> Path | None:
        for path in (
            self.contract_test_path,
            self.cpp_contract_test_path,
            self.legacy_contract_test_path,
        ):
            if path.is_file():
                return path
        return None

    def relative(self, path: str | Path) -> str:
        return Path(path).resolve().relative_to(self.root).as_posix()

    def correctness_spec_relative(self) -> str:
        return self.relative(self.correctness_spec())

    def benchmark_spec_relative(self) -> str:
        return self.relative(self.benchmark_spec())


def _prefer_existing(primary: Path, legacy: Path) -> Path:
    return primary if primary.exists() else legacy
