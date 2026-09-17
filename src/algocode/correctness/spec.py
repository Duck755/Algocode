"""Validated correctness specification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from algocode.domain.errors import ConfigError
from algocode.domain.model import ComparisonMode, CorrectnessMode

DEFAULT_PROTECTED_FILES = (
    "tests/",
    ".algocode/oracle/",
    ".algocode/benchmarks/",
    ".algocode/config.yaml",
    ".algocode/contract.json",
    "oracle/",
    "generator/",
    "hidden-tests/",
    "benchmarks/",
    ".algocode.yaml",
)


class CorrectnessCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    input: str = ""
    expected_output: str | None = None
    expected_exit_code: int = 0
    args: tuple[str, ...] = ()
    timeout_seconds: int | None = Field(default=None, gt=0)


class CorrectnessSpec(BaseModel):
    """Frozen, hashable correctness contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(default=1, ge=1)
    mode: CorrectnessMode = CorrectnessMode.CASES
    run_command: tuple[str, ...] = ()
    source_root: str = "."
    oracle_command: tuple[str, ...] = ()
    generator_command: tuple[str, ...] = ()
    checker_command: tuple[str, ...] = ()
    cases: tuple[CorrectnessCase, ...] = ()
    iterations: int = Field(default=10, gt=0)
    seed: int = 0
    timeout_seconds: int = Field(default=10, gt=0)
    comparison: ComparisonMode = ComparisonMode.EXACT
    float_tolerance: float = Field(default=1e-9, ge=0)
    require_determinism: bool = True
    visible_to_agent: bool = True
    protected_files: tuple[str, ...] = DEFAULT_PROTECTED_FILES

    @model_validator(mode="after")
    def validate_mode_inputs(self) -> CorrectnessSpec:
        if self.mode is CorrectnessMode.CASES and not self.cases:
            raise ValueError("cases mode requires at least one case")
        if (
            self.mode is CorrectnessMode.CASES
            and not self.oracle_command
            and any(case.expected_output is None for case in self.cases)
        ):
            raise ValueError("cases without expected_output require oracle_command")
        if self.mode is CorrectnessMode.ORACLE and not self.oracle_command:
            raise ValueError("oracle mode requires oracle_command")
        if self.mode is CorrectnessMode.STRESS and not self.generator_command:
            raise ValueError("stress mode requires generator_command")
        if self.mode is CorrectnessMode.STRESS and not self.oracle_command:
            raise ValueError("stress mode requires oracle_command")
        if self.mode is CorrectnessMode.HYBRID and not self.cases and not self.oracle_command:
            raise ValueError("hybrid mode requires cases or oracle_command")
        if (
            self.mode is CorrectnessMode.HYBRID
            and not self.oracle_command
            and any(case.expected_output is None for case in self.cases)
        ):
            raise ValueError("hybrid cases without expected_output require oracle_command")
        if self.comparison is ComparisonMode.CHECKER_COMMAND and not self.checker_command:
            raise ValueError("checker-command comparison requires checker_command")
        return self


def load_correctness_spec(path: str | Path) -> CorrectnessSpec:
    spec_path = Path(path).expanduser()
    try:
        raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"failed to read correctness spec {spec_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("correctness spec must contain a YAML mapping")
    try:
        return CorrectnessSpec.model_validate(raw)
    except ValueError as exc:
        raise ConfigError(f"invalid correctness spec: {exc}") from exc


def compute_spec_hash(spec: CorrectnessSpec) -> str:
    payload = spec.model_dump(mode="json")
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
