"""Validated configuration models."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

CONFIG_DICT = ConfigDict(
    alias_generator=to_camel,
    populate_by_name=True,
    extra="forbid",
    frozen=True,
    hide_input_in_errors=True,
)

_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CREDENTIAL_NAME = re.compile(r"[A-Za-z0-9_.-]+")

PolicyEffect = Literal["allow", "ask", "deny"]
PolicyLayer = Literal["hard", "managed", "user", "project", "default"]


class ProjectConfig(BaseModel):
    model_config = CONFIG_DICT

    language: str = "auto"
    source_root: str = "."


class ProviderConfig(BaseModel):
    model_config = CONFIG_DICT

    type: str = "openai-compatible"
    base_url: str | None = None
    api_key_env: str | None = None
    credential_ref: str | None = None

    @field_validator("credential_ref")
    @classmethod
    def validate_credential_ref(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value.startswith("env://"):
            name = value.removeprefix("env://")
            if _ENV_NAME.fullmatch(name) is None:
                raise ValueError("env credential_ref must reference a valid environment variable")
            return value
        if value.startswith("local://"):
            name = value.removeprefix("local://")
            if _CREDENTIAL_NAME.fullmatch(name) is None:
                raise ValueError("local credential_ref must reference a valid credential name")
            return value
        raise ValueError("credential_ref must use env://<NAME> or local://<NAME>")

    @field_validator("api_key_env")
    @classmethod
    def validate_api_key_env(cls, value: str | None) -> str | None:
        if value is not None and _ENV_NAME.fullmatch(value) is None:
            raise ValueError("api_key_env must be an environment variable name, not a secret value")
        return value


class ModelConfig(BaseModel):
    model_config = CONFIG_DICT

    provider: str = "default"
    model: str
    context_window: int = Field(default=128_000, gt=0)


class DefaultsConfig(BaseModel):
    model_config = CONFIG_DICT

    provider: str = "default"
    model: str = "default"


class RuntimeConfig(BaseModel):
    model_config = CONFIG_DICT

    max_steps_per_phase: int = Field(default=30, gt=0)
    max_tool_calls_per_phase: int = Field(default=50, gt=0)
    max_candidates: int = Field(default=3, gt=0)
    network: bool = False


class CorrectnessConfig(BaseModel):
    model_config = CONFIG_DICT

    mode: str = "hybrid"
    require_determinism: bool = True
    protected_files: tuple[str, ...] = (
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


class BenchmarkDefaults(BaseModel):
    model_config = CONFIG_DICT

    method: str = "process"
    warmup: int = Field(default=5, ge=0)
    repeats: int = Field(default=15, gt=0)
    primary_metric: str = "wall_time"
    direction: str = "minimize"


class AcceptancePolicyConfig(BaseModel):
    model_config = CONFIG_DICT

    require_correctness: bool = True
    require_statistically_significant: bool = True
    min_median_improvement_percent: float = 2.0
    max_peak_memory_regression_percent: float | None = Field(default=None, ge=0)
    max_compile_time_regression_percent: float | None = Field(default=None, ge=0)
    max_variation_percent: float | None = Field(default=5.0, gt=0)


class PolicyRuleConfig(BaseModel):
    model_config = CONFIG_DICT

    action: str
    resource: str = "*"
    effect: PolicyEffect = "ask"
    layer: PolicyLayer = "project"


class ApprovalConfig(BaseModel):
    model_config = CONFIG_DICT

    mode: Literal["non-interactive", "interactive"] = "non-interactive"


class SandboxConfig(BaseModel):
    model_config = CONFIG_DICT

    mode: Literal["trusted-local", "process"] = "process"
    backend: Literal["auto", "native", "docker", "wsl2", "disabled"] = "auto"
    image: str = "algocode-sandbox:latest"
    wsl_distro: str = "Ubuntu"
    network: bool = False
    timeout_seconds: int = Field(default=120, gt=0)
    max_output_bytes: int = Field(default=1_000_000, gt=0)
    memory_mb: int = Field(default=2048, gt=0)
    cpus: float = Field(default=2.0, gt=0)
    pids_limit: int = Field(default=256, gt=0)
    read_only_root: bool = True
    tmpfs_size_mb: int = Field(default=64, gt=0)
    allowed_env: tuple[str, ...] = ("PATH", "PATHEXT", "SYSTEMROOT", "TEMP", "TMP")


class PolicyConfig(BaseModel):
    model_config = CONFIG_DICT

    approval: ApprovalConfig = Field(default_factory=ApprovalConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    rules: tuple[PolicyRuleConfig, ...] = ()
    default_effect: PolicyEffect = "ask"


class StorageConfig(BaseModel):
    model_config = CONFIG_DICT

    artifact_retention_days: int = Field(default=90, gt=0)


class AlgocodeConfig(BaseModel):
    """Fully resolved, immutable application configuration."""

    model_config = CONFIG_DICT

    version: int = Field(default=1, ge=1)
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    models: dict[str, ModelConfig] = Field(default_factory=dict)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    correctness: CorrectnessConfig = Field(default_factory=CorrectnessConfig)
    benchmark: BenchmarkDefaults = Field(default_factory=BenchmarkDefaults)
    benchmarks: dict[str, BenchmarkDefaults] = Field(default_factory=dict)
    acceptance_policy: AcceptancePolicyConfig = Field(default_factory=AcceptancePolicyConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
