"""Repeatable P0 acceptance and release gate."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from algocode.acceptance.matrix import load_requirements, validate_requirement_paths
from algocode.acceptance.probe import ProbeMetrics, run_release_probe
from algocode.acceptance.types import AcceptanceReport, GateCheck

SUITE_GROUPS: dict[str, tuple[str, ...]] = {
    "unit": ("tests/unit",),
    "contract": ("tests/contract",),
    "integration": (
        "tests/integration",
        "--ignore=tests/integration/test_e2e_full.py",
        "--ignore=tests/integration/test_eval_service.py",
    ),
    "e2e": ("tests/integration/test_e2e_full.py",),
    "eval": ("tests/integration/test_eval_service.py",),
}
ZERO_METRICS = (
    "false_accept_count",
    "policy_violation_count",
    "protected_file_change_count",
    "replay_divergence_count",
    "event_sequence_gap_count",
    "apply_rollback_failure_count",
)


class AcceptanceService:
    def __init__(
        self,
        root: str | Path,
        *,
        report_dir: str | Path | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.report_dir = (
            Path(report_dir).resolve()
            if report_dir is not None
            else self.root / "docs" / "acceptance" / "P0"
        )

    def run(self, *, run_tests: bool = True) -> AcceptanceReport:
        checks: list[GateCheck] = []
        requirements = ()
        mapping_ok = True
        try:
            requirements = load_requirements(self.root)
            requirements = validate_requirement_paths(self.root, requirements)
            checks.append(
                GateCheck(
                    id="matrix.mapping",
                    category="traceability",
                    passed=True,
                    message=f"mapped {len(requirements)} P0 requirements",
                    metrics={"requirements_total": len(requirements)},
                )
            )
        except ValueError as exc:
            mapping_ok = False
            checks.append(
                GateCheck(
                    id="matrix.mapping",
                    category="traceability",
                    passed=False,
                    message=str(exc),
                )
            )

        if run_tests:
            checks.extend(self._run_test_suites())
        else:
            checks.append(
                GateCheck(
                    id="suite.skipped",
                    category="test",
                    passed=True,
                    message="test suites skipped by request",
                )
            )

        try:
            probe = run_release_probe(self.root)
            checks.extend(_probe_checks(probe))
        except Exception as exc:
            probe = None
            checks.append(
                GateCheck(
                    id="probe.release_evidence",
                    category="evidence",
                    passed=False,
                    message=f"release evidence probe failed: {exc}",
                )
            )

        metrics = _metrics(probe)
        status = "PASS" if mapping_ok and all(check.passed for check in checks) else "FAIL"
        report = AcceptanceReport(
            schema_version=1,
            report_id=f"acceptance_{uuid4().hex}",
            generated_at=datetime.now(UTC).isoformat(),
            status=status,
            requirements_total=len(requirements),
            requirements_mapped=len(requirements) if mapping_ok else 0,
            checks=tuple(checks),
            metrics=metrics,
        )
        self.persist(report)
        return report

    def persist(self, report: AcceptanceReport) -> tuple[Path, Path]:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.report_dir / "report.json"
        markdown_path = self.report_dir / "report.md"
        json_path.write_text(
            json.dumps(report.payload(), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        markdown_path.write_text(render_acceptance_markdown(report), encoding="utf-8")
        return json_path, markdown_path

    def _run_test_suites(self) -> list[GateCheck]:
        checks: list[GateCheck] = []
        for name, arguments in SUITE_GROUPS.items():
            started = time.perf_counter()
            completed = subprocess.run(
                (sys.executable, "-m", "pytest", "-q", *arguments),
                cwd=self.root,
                check=False,
                capture_output=True,
                text=True,
                timeout=1800,
            )
            output = f"{completed.stdout}\n{completed.stderr}".strip()
            checks.append(
                GateCheck(
                    id=f"suite.{name}",
                    category="test",
                    passed=completed.returncode == 0,
                    message=f"{name} exit code {completed.returncode}",
                    metrics={"duration_seconds": time.perf_counter() - started},
                    output_tail=output[-4000:],
                )
            )
        return checks


def _probe_checks(probe: ProbeMetrics) -> list[GateCheck]:
    return [
        GateCheck(
            id="metric.false_accept",
            category="evidence",
            passed=probe.false_accept_count == 0,
            message=f"false accept count = {probe.false_accept_count}",
            metrics={"false_accept_count": probe.false_accept_count},
        ),
        GateCheck(
            id="metric.policy_violation",
            category="evidence",
            passed=probe.policy_violation_count == 0,
            message=f"policy violation count = {probe.policy_violation_count}",
            metrics={"policy_violation_count": probe.policy_violation_count},
        ),
        GateCheck(
            id="metric.protected_file_change",
            category="evidence",
            passed=probe.protected_file_change_count == 0,
            message=f"protected file change count = {probe.protected_file_change_count}",
            metrics={"protected_file_change_count": probe.protected_file_change_count},
        ),
        GateCheck(
            id="metric.replay_divergence",
            category="evidence",
            passed=probe.replay_divergence_count == 0,
            message=f"replay divergence count = {probe.replay_divergence_count}",
            metrics={"replay_divergence_count": probe.replay_divergence_count},
        ),
        GateCheck(
            id="metric.event_sequence_gap",
            category="evidence",
            passed=probe.event_sequence_gap_count == 0,
            message=f"event sequence gap count = {probe.event_sequence_gap_count}",
            metrics={
                "event_sequence_gap_count": probe.event_sequence_gap_count,
                "event_count": probe.event_count,
            },
        ),
        GateCheck(
            id="metric.apply_rollback_failure",
            category="evidence",
            passed=probe.apply_rollback_failure_count == 0,
            message=f"apply/rollback failure count = {probe.apply_rollback_failure_count}",
            metrics={
                "apply_rollback_failure_count": probe.apply_rollback_failure_count,
                "task_status": probe.task_status,
            },
        ),
    ]


def _metrics(probe: ProbeMetrics | None) -> dict[str, int | float | str | None]:
    if probe is None:
        return {name: None for name in ZERO_METRICS}
    return {
        "false_accept_count": probe.false_accept_count,
        "policy_violation_count": probe.policy_violation_count,
        "protected_file_change_count": probe.protected_file_change_count,
        "replay_divergence_count": probe.replay_divergence_count,
        "event_sequence_gap_count": probe.event_sequence_gap_count,
        "apply_rollback_failure_count": probe.apply_rollback_failure_count,
        "event_count": probe.event_count,
        "task_status": probe.task_status,
    }


def render_acceptance_markdown(report: AcceptanceReport) -> str:
    lines = [
        f"# P0 Acceptance Report {report.report_id}",
        "",
        f"- Status: `{report.status}`",
        f"- Generated at: {report.generated_at}",
        f"- Requirements mapped: {report.requirements_mapped}/{report.requirements_total}",
        "",
        "## Release Metrics",
        "",
    ]
    for key, value in report.metrics.items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Gate Checks", ""])
    for check in report.checks:
        state = "PASS" if check.passed else "FAIL"
        lines.append(f"- [{state}] `{check.id}` ({check.category}): {check.message}")
        if check.output_tail:
            lines.extend(["", "```text", check.output_tail, "```", ""])
    return "\n".join(lines) + "\n"
