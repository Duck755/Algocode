"""Validated benchmark specification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from algocode.domain.errors import ConfigError
from algocode.domain.model import BenchmarkMetric, BenchmarkScope


class BenchmarkInputCase(BaseModel):
    """One named input in a benchmark input matrix."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    input: str = ""


class BenchmarkSpec(BaseModel):
    """Frozen benchmark contract shared by all language adapters."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(default=1, ge=1)
    scope: BenchmarkScope = BenchmarkScope.STDIN
    run_command: tuple[str, ...] = ()
    source_root: str = "."
    input: str = ""
    inputs: tuple[BenchmarkInputCase, ...] = ()
    warmup: int = Field(default=5, ge=0)
    repeats: int = Field(default=15, gt=0)
    timeout_seconds: int = Field(default=30, gt=0)
    metric: BenchmarkMetric = BenchmarkMetric.WALL_TIME
    direction: str = "minimize"
    network: bool = False
    max_variation_percent: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_scope(self) -> BenchmarkSpec:
        if self.scope is BenchmarkScope.FUNCTION:
            raise ValueError("function benchmark scope is not enabled in M4")
        if self.direction not in {"minimize", "maximize"}:
            raise ValueError("direction must be minimize or maximize")
        if self.input and self.inputs:
            raise ValueError("use either input or inputs, not both")
        input_ids = [case.id for case in self.inputs]
        if len(input_ids) != len(set(input_ids)):
            raise ValueError("benchmark input ids must be unique")
        return self

    def effective_inputs(self) -> tuple[BenchmarkInputCase, ...]:
        if self.inputs:
            return self.inputs
        return (BenchmarkInputCase(id="default", input=self.input),)


def load_benchmark_spec(path: str | Path) -> BenchmarkSpec:
    spec_path = Path(path).expanduser()
    try:
        raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"failed to read benchmark spec {spec_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("benchmark spec must contain a YAML mapping")
    try:
        return BenchmarkSpec.model_validate(raw)
    except ValueError as exc:
        raise ConfigError(f"invalid benchmark spec: {exc}") from exc


def compute_benchmark_spec_hash(spec: BenchmarkSpec) -> str:
    payload = spec.model_dump(mode="json", exclude={"inputs"})
    if spec.inputs:
        payload["inputs"] = [
            {"id": case.id, "input": case.input} for case in spec.inputs
        ]
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_comparison_key(
    *,
    spec_hash: str,
    input_hash: str,
    environment_hash: str,
) -> str:
    payload = {
        "spec_hash": spec_hash,
        "input_hash": input_hash,
        "environment_hash": environment_hash,
    }
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_input_hash(spec: BenchmarkSpec) -> str:
    payload = {
        "command": list(spec.run_command),
        "input": spec.input,
        "scope": spec.scope.value,
    }
    if spec.inputs:
        payload["input_cases"] = [
            {"id": case.id, "input": case.input} for case in spec.inputs
        ]
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
