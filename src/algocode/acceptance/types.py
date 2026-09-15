"""Acceptance gate types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Requirement:
    id: str
    title: str
    implementation: tuple[str, ...]
    tests: tuple[str, ...]
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GateCheck:
    id: str
    category: str
    passed: bool
    message: str
    metrics: dict[str, float | int | str | None] = field(default_factory=dict)
    output_tail: str = ""


@dataclass(frozen=True, slots=True)
class AcceptanceReport:
    schema_version: int
    report_id: str
    generated_at: str
    status: str
    requirements_total: int
    requirements_mapped: int
    checks: tuple[GateCheck, ...]
    metrics: dict[str, int | float | str | None]

    def payload(self) -> dict[str, object]:
        return {
            "schemaVersion": self.schema_version,
            "reportId": self.report_id,
            "generatedAt": self.generated_at,
            "status": self.status,
            "requirementsTotal": self.requirements_total,
            "requirementsMapped": self.requirements_mapped,
            "checks": [
                {
                    "id": check.id,
                    "category": check.category,
                    "passed": check.passed,
                    "message": check.message,
                    "metrics": check.metrics,
                    "outputTail": check.output_tail,
                }
                for check in self.checks
            ],
            "metrics": self.metrics,
        }
