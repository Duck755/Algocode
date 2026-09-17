"""Runtime-validated optimization plan types."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from algocode.structured_output import parse_model


class PlanStep(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    id: str
    description: str = ""
    action: str = ""
    files: tuple[str, ...] = ()
    expected_effect: str = ""
    verification: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_description(self) -> PlanStep:
        description = self.description.strip() or self.action.strip()
        if not description:
            raise ValueError("plan step requires description or action")
        if description != self.description:
            object.__setattr__(self, "description", description)
        return self


class RetryDecision(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    mode: Literal["continue", "pivot", "rollback"]
    based_on_attempt: int = Field(gt=0)
    parent_attempt: int = Field(ge=0)
    direction_id: str
    direction_state: Literal["active", "exhausted", "abandoned"] = "active"
    reason: str
    preserve_changes: tuple[str, ...] = ()


class OptimizationPlan(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    schema_version: int = Field(default=1, ge=1)
    summary: str
    strategy: str
    rationale: str = ""
    steps: tuple[PlanStep, ...] = Field(min_length=1)
    constraints: tuple[str, ...] = ()
    protected_files: tuple[str, ...] = ()
    benchmark_plan: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    retry_decision: RetryDecision | None = None


def parse_optimization_plan(text: str) -> OptimizationPlan:
    return parse_model(text, OptimizationPlan, label="optimization plan response")
