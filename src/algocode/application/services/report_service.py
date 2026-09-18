"""Canonical task report generation."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from algocode.application.services.baseline_service import BaselineService
from algocode.application.services.benchmark_service import BenchmarkService
from algocode.application.services.candidate_service import CandidateService
from algocode.application.services.correctness_service import CorrectnessService
from algocode.application.services.decision_service import DecisionService
from algocode.application.services.project_service import ProjectService
from algocode.application.services.task_service import TaskService
from algocode.domain.events import EventEnvelope, EventType
from algocode.ports import ArtifactStore, EventStore
from algocode.security import SecretRedactor


class ReportService:
    """Build immutable JSON and Markdown reports from durable evidence."""

    def __init__(
        self,
        *,
        event_store: EventStore,
        task_service: TaskService,
        project_service: ProjectService,
        baseline_service: BaselineService,
        candidate_service: CandidateService,
        correctness_service: CorrectnessService,
        benchmark_service: BenchmarkService,
        decision_service: DecisionService,
        artifact_store: ArtifactStore,
        redactor: SecretRedactor | None = None,
    ) -> None:
        self._event_store = event_store
        self._task_service = task_service
        self._project_service = project_service
        self._baseline_service = baseline_service
        self._candidate_service = candidate_service
        self._correctness_service = correctness_service
        self._benchmark_service = benchmark_service
        self._decision_service = decision_service
        self._artifact_store = artifact_store
        self._redactor = redactor or SecretRedactor()

    async def build(self, task_id: str) -> tuple[dict[str, object], str, dict[str, object]]:
        task = await self._task_service.get_task(task_id)
        project = await self._project_service.get(task.project_id)
        baseline = await self._baseline_service.get_for_task(task.id)
        candidates = await self._candidate_service.list_for_task(task.id)
        correctness_runs = await self._correctness_service.list_for_task(task.id)
        benchmark_runs = await self._benchmark_service.list_for_task(task.id)
        generated_at = datetime.now(UTC)
        selected_candidate_id = task.active_candidate_id
        candidate_payloads: list[dict[str, object]] = []
        decisions: list[dict[str, object]] = []
        comparisons: list[dict[str, object]] = []
        artifact_refs: list[dict[str, str]] = []
        for candidate in candidates:
            decision = await self._decision_service.get_for_candidate(candidate.id)
            if decision is not None:
                decisions.append(
                    {
                        "decision_id": str(decision.id),
                        "candidate_id": str(decision.candidate_id),
                        "outcome": decision.outcome.value,
                        "reason": decision.reason,
                        "decided_at": decision.decided_at.isoformat(),
                        "evidence_refs": [_ref_payload(ref) for ref in decision.evidence_refs],
                    }
                )
                selected_candidate_id = selected_candidate_id or (
                    candidate.id if decision.outcome.value == "accepted" else None
                )
            candidate_payloads.append(
                {
                    "candidate_id": str(candidate.id),
                    "status": candidate.status.value,
                    "base_revision": candidate.base_revision.value,
                    "base_snapshot_hash": candidate.base_snapshot_hash,
                    "parent_candidate_id": (
                        str(candidate.parent_candidate_id)
                        if candidate.parent_candidate_id is not None
                        else None
                    ),
                    "fork_snapshot_hash": candidate.fork_snapshot_hash,
                    "apply_base_revision": (
                        candidate.apply_base_revision.value
                        if candidate.apply_base_revision is not None
                        else None
                    ),
                    "apply_base_snapshot_hash": candidate.apply_base_snapshot_hash,
                    "workspace_ref": candidate.workspace_ref,
                    "patch_hash": candidate.patch_hash,
                    "created_at": candidate.created_at.isoformat(),
                    "frozen_at": (
                        candidate.frozen_at.isoformat() if candidate.frozen_at is not None else None
                    ),
                }
            )
        for run in benchmark_runs:
            if run.result_ref is None:
                continue
            payload = await self._benchmark_service.read_result(run)
            if run.target_kind == "candidate":
                comparisons.append(payload.get("comparison") or {})
        report_id = f"report_{uuid4().hex}"
        payload: dict[str, object] = {
            "schemaVersion": 1,
            "reportId": report_id,
            "taskId": str(task.id),
            "generatedAt": generated_at.isoformat(),
            "objective": task.objective,
            "finalStatus": task.status.value,
            "selectedCandidateId": selected_candidate_id,
            "project": {
                "projectId": str(project.id),
                "name": project.name,
                "rootPath": project.root_path,
                "language": project.language.value,
                "gitRevision": project.git_revision,
            },
            "baseline": (
                None
                if baseline is None
                else {
                    "baselineId": baseline.id,
                    "revision": baseline.revision.value,
                    "snapshotHash": baseline.snapshot_hash,
                    "environmentHash": baseline.environment_hash,
                    "buildResultRef": _optional_ref_payload(baseline.build_result_ref),
                    "correctnessResultRef": _optional_ref_payload(baseline.correctness_result_ref),
                    "benchmarkResultRef": _optional_ref_payload(baseline.benchmark_result_ref),
                }
            ),
            "environment": (
                None if baseline is None else {"environmentHash": baseline.environment_hash}
            ),
            "candidates": candidate_payloads,
            "experiments": [
                {
                    "benchmarkRunId": run.id,
                    "targetKind": run.target_kind,
                    "targetId": run.target_id,
                    "status": run.status.value,
                    "comparisonKey": run.comparison_key,
                    "resultRef": _optional_ref_payload(run.result_ref),
                    "comparisonRef": _optional_ref_payload(run.comparison_ref),
                }
                for run in benchmark_runs
            ],
            "comparison": comparisons[-1] if comparisons else None,
            "decision": decisions[-1] if decisions else None,
            "correctnessEvidence": [
                {
                    "resultId": run.id,
                    "targetKind": run.target_kind,
                    "targetId": run.target_id,
                    "status": run.status.value,
                    "failureKind": (
                        run.failure_kind.value if run.failure_kind is not None else None
                    ),
                    "resultRef": _optional_ref_payload(run.result_ref),
                }
                for run in correctness_runs
            ],
            "benchmarkEvidence": [
                {
                    "runId": run.id,
                    "targetKind": run.target_kind,
                    "targetId": run.target_id,
                    "status": run.status.value,
                    "resultRef": _optional_ref_payload(run.result_ref),
                    "comparisonRef": _optional_ref_payload(run.comparison_ref),
                }
                for run in benchmark_runs
            ],
            "tradeoffs": [],
            "limitations": [],
            "artifactRefs": artifact_refs,
        }
        for key in ("baseline", "correctnessEvidence", "benchmarkEvidence"):
            _collect_refs(payload.get(key), artifact_refs)
        payload = self._redactor.redact_value(payload)
        canonical = canonical_json(payload)
        json_ref = await self._artifact_store.put(
            canonical,
            kind="task-report-json",
            mime_type="application/json",
            metadata={"task_id": str(task.id), "report_id": report_id},
        )
        markdown = render_markdown(payload)
        root_markdown_path = _write_root_markdown(project.root_path, markdown)
        markdown_ref = await self._artifact_store.put(
            markdown.encode("utf-8"),
            kind="task-report-markdown",
            mime_type="text/markdown",
            metadata={"task_id": str(task.id), "report_id": report_id},
        )
        seq = await self._next_seq(str(task.id))
        await self._event_store.append(
            str(task.id),
            seq - 1,
            (
                EventEnvelope(
                    id=f"evt_{uuid4().hex}",
                    aggregate_id=str(task.id),
                    seq=seq,
                    type=EventType.REPORT_GENERATED,
                    payload={
                        "report_id": report_id,
                        "json_ref": _ref_payload(json_ref),
                        "markdown_ref": _ref_payload(markdown_ref),
                    },
                ),
            ),
        )
        return (
            payload,
            markdown,
            {
                "json_ref": _ref_payload(json_ref),
                "markdown_ref": _ref_payload(markdown_ref),
                "root_markdown_path": str(root_markdown_path),
            },
        )

    async def _next_seq(self, aggregate_id: str) -> int:
        events = await self._event_store.read(aggregate_id)
        return events[-1].seq + 1 if events else 1


def _write_root_markdown(project_root: str | Path, markdown: str) -> Path:
    root = Path(project_root).resolve()
    path = root / "report.md"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(markdown, encoding="utf-8")
    temporary.replace(path)
    _ensure_local_exclude(root, "report.md")
    return path


def _ensure_local_exclude(project_root: Path, pattern: str) -> None:
    git_dir = project_root / ".git"
    if not git_dir.is_dir():
        return
    exclude_path = git_dir / "info" / "exclude"
    exclude_path.parent.mkdir(parents=True, exist_ok=True)
    existing = (
        exclude_path.read_text(encoding="utf-8", errors="replace")
        if exclude_path.exists()
        else ""
    )
    lines = existing.splitlines()
    if pattern in lines:
        return
    content = "\n".join([*lines, pattern]).rstrip() + "\n"
    exclude_path.write_text(content, encoding="utf-8")


def canonical_json(payload: dict[str, object]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def report_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def render_markdown(payload: dict[str, object]) -> str:
    baseline = payload.get("baseline") or {}
    comparison = payload.get("comparison") or {}
    decision = payload.get("decision") or {}
    candidates = payload.get("candidates") or []
    lines = [
        f"# Algocode Report {payload['reportId']}",
        "",
        f"- Task: `{payload['taskId']}`",
        f"- Objective: {payload['objective']}",
        f"- Final status: `{payload['finalStatus']}`",
        f"- Selected candidate: `{payload.get('selectedCandidateId') or 'none'}`",
        f"- Candidates: {len(candidates)}",
        "",
        "## Baseline",
        "",
        f"- Baseline ID: `{baseline.get('baselineId', 'none')}`",
        f"- Revision: `{baseline.get('revision', 'none')}`",
        f"- Snapshot hash: `{baseline.get('snapshotHash', 'none')}`",
        "",
        "## Comparison",
        "",
    ]
    if comparison:
        lines.extend(
            [
                f"- Baseline median: {comparison.get('baseline_median')}",
                f"- Candidate median: {comparison.get('candidate_median')}",
                f"- Improvement: {comparison.get('improvement_percent')}%",
                f"- Valid: {comparison.get('valid')}",
            ]
        )
    else:
        lines.append("- No benchmark comparison available.")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            (
                f"- Outcome: `{decision.get('outcome', 'none')}`"
                if decision
                else "- No decision recorded."
            ),
            "",
            "## Limitations",
            "",
        ]
    )
    limitations = payload.get("limitations") or []
    lines.extend(f"- {item}" for item in limitations) if limitations else lines.append(
        "- None recorded."
    )
    return "\n".join(lines) + "\n"


def _optional_ref_payload(ref) -> dict[str, str] | None:
    return None if ref is None else _ref_payload(ref)


def _ref_payload(ref) -> dict[str, str]:
    return {"uri": ref.uri, "sha256": ref.sha256}


def _collect_refs(value: object, target: list[dict[str, str]]) -> None:
    if isinstance(value, dict):
        if "uri" in value and "sha256" in value:
            item = {"uri": str(value["uri"]), "sha256": str(value["sha256"])}
            if item not in target:
                target.append(item)
            return
        for child in value.values():
            _collect_refs(child, target)
    elif isinstance(value, list):
        for child in value:
            _collect_refs(child, target)
