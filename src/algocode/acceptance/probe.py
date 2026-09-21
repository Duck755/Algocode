"""Release evidence probe for the P0 acceptance gate."""

from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path

from algocode.application.services.decision_service import DecisionService
from algocode.benchmark.spec import BenchmarkSpec
from algocode.bootstrap import build_context
from algocode.config.model import AcceptancePolicyConfig
from algocode.correctness.spec import CorrectnessCase, CorrectnessSpec
from algocode.domain.errors import DecisionError
from algocode.domain.model import TaskPhase
from algocode.policy.types import PolicyEffect, PolicyRequest
from algocode.process_output import run_text
from algocode.tools.types import ToolContext


def _init_git_repository(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for relative_path, content in files.items():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "algocode-acceptance@example.test")
    _git(root, "config", "user.name", "Algocode Acceptance")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "initial")
    return root


def _git(root: Path, *args: str) -> None:
    run_text(("git", *args), cwd=root, check=True, capture_output=True)


@dataclass(frozen=True, slots=True)
class ProbeMetrics:
    false_accept_count: int
    policy_violation_count: int
    protected_file_change_count: int
    replay_divergence_count: int
    event_sequence_gap_count: int
    apply_rollback_failure_count: int
    noise_false_accept_count: int
    minimal_gain_detection_count: int
    event_count: int
    task_status: str


async def collect_release_evidence(root: str | Path) -> ProbeMetrics:
    with tempfile.TemporaryDirectory(
        prefix=f"algocode-acceptance-{Path(root).name}-",
        ignore_cleanup_errors=True,
    ) as directory:
        return await _run_probe(Path(directory))


async def _run_probe(root: Path) -> ProbeMetrics:
    project_root = _init_git_repository(
        root / "project",
        {"main.py": "import time\ntime.sleep(0.05)\nprint('hello')\n"},
    )
    (project_root / ".algocode.yaml").write_text(
        (
            "acceptancePolicy:\n"
            "  minMedianImprovementPercent: -1000\n"
            "  requireStatisticallySignificant: false\n"
        ),
        encoding="utf-8",
    )
    context = build_context(project_root=project_root, data_dir=root / "data")
    project = await context.project_service.register(project_root, write_config=True)
    task = await context.task_service.create_task(
        "P0 release evidence",
        project_id=project.id,
    )
    await context.baseline_service.capture(task.id)
    await context.correctness_service.run_baseline(
        task.id,
        CorrectnessSpec(
            mode="cases",
            comparison="line-trim",
            cases=(CorrectnessCase(id="baseline", expected_output="hello"),),
        ),
    )
    benchmark_spec = BenchmarkSpec(warmup=0, repeats=1)
    await context.benchmark_service.run_baseline(task.id, benchmark_spec)

    apply_rollback_failures = 0
    replay_divergence = 0
    protected_file_changes = 0

    candidate = await context.candidate_service.create(task.id)
    (Path(candidate.workspace_ref) / "main.py").write_text(
        "print('hi')\n",
        encoding="utf-8",
    )
    candidate = await context.candidate_service.freeze(candidate.id)
    correctness_run, correctness = await context.correctness_service.run_target(
        task.id,
        CorrectnessSpec(
            mode="cases",
            comparison="line-trim",
            cases=(CorrectnessCase(id="candidate", expected_output="hi"),),
        ),
        target_kind="candidate",
        target_id=str(candidate.id),
        workspace_ref=candidate.workspace_ref,
    )
    if not correctness.passed:
        replay_divergence += 1
    else:
        _, replay = await context.correctness_service.replay(correctness_run.id)
        replay_divergence += int(not replay.passed)
    await context.benchmark_service.run_candidate(
        task.id,
        str(candidate.id),
        candidate.workspace_ref,
        correctness_run.id,
        benchmark_spec,
    )
    await context.decision_service.accept(task.id, candidate.id)
    await context.report_service.build(task.id)

    try:
        applied = await context.apply_service.apply(task.id, candidate.id)
        apply_rollback_failures += int(not applied.get("applied", False))
        rolled_back = await context.apply_service.rollback(task.id, candidate.id)
        apply_rollback_failures += int(not rolled_back.get("rolled_back", False))
    except Exception:
        apply_rollback_failures += 1

    policy = context.policy_engine.evaluate(
        PolicyRequest(
            action="file.write",
            resource="tests/test_main.py",
            tool_name="apply_patch",
        )
    )
    policy_violations = int(policy.effect is not PolicyEffect.DENY)

    protected_context = ToolContext(
        task=task,
        phase=TaskPhase.IMPLEMENT,
        workspace=Path(candidate.workspace_ref),
        candidate_id=str(candidate.id),
        artifact_store=context.artifact_store,
        language_registry=context.language_registry,
        correctness_service=context.correctness_service,
        benchmark_service=context.benchmark_service,
        protected_files=context.config.correctness.protected_files,
    )
    protected_patch = await context.tool_registry.execute(
        "apply_patch",
        {
            "patch": (
                "diff --git a/tests/test_main.py b/tests/test_main.py\n"
                "--- a/tests/test_main.py\n"
                "+++ b/tests/test_main.py\n"
                "@@ -1 +1 @@\n"
                "-assert True\n"
                "+assert False\n"
            )
        },
        protected_context,
    )
    if protected_patch.status == "success":
        protected_file_changes += 1

    false_accepts = 0
    unverified = await context.candidate_service.create(task.id)
    (Path(unverified.workspace_ref) / "main.py").write_text(
        "print('unverified')\n",
        encoding="utf-8",
    )
    unverified = await context.candidate_service.freeze(unverified.id)
    await context.correctness_service.run_target(
        task.id,
        CorrectnessSpec(
            mode="cases",
            comparison="line-trim",
            cases=(CorrectnessCase(id="unverified", expected_output="unverified"),),
        ),
        target_kind="candidate",
        target_id=str(unverified.id),
        workspace_ref=unverified.workspace_ref,
    )
    try:
        await context.decision_service.accept(task.id, unverified.id)
        false_accepts += 1
    except DecisionError:
        pass

    noise_false_accepts, minimal_gain_detections = _policy_scenario_metrics()

    events = await context.event_store.read(str(task.id))
    gaps = sum(1 for expected, event in enumerate(events, start=1) if event.seq != expected)
    task_after = await context.task_service.get_task(task.id)
    return ProbeMetrics(
        false_accept_count=false_accepts,
        policy_violation_count=policy_violations,
        protected_file_change_count=protected_file_changes,
        replay_divergence_count=replay_divergence,
        event_sequence_gap_count=gaps,
        apply_rollback_failure_count=apply_rollback_failures,
        noise_false_accept_count=noise_false_accepts,
        minimal_gain_detection_count=minimal_gain_detections,
        event_count=len(events),
        task_status=task_after.status.value,
    )


def _policy_scenario_metrics() -> tuple[int, int]:
    """Return (noise false accepts, minimal 5% gain detections)."""
    service = DecisionService(
        event_store=object(),
        database=object(),
        task_service=object(),
        candidate_service=object(),
        correctness_service=object(),
        benchmark_service=object(),
        decision_projection=object(),
        acceptance_policy=AcceptancePolicyConfig(
            min_median_improvement_percent=5.0,
            max_variation_percent=5.0,
            require_statistically_significant=False,
        ),
    )
    noise_false_accepts = 0
    minimal_gain_detections = 0

    try:
        service._validate_acceptance_thresholds(
            {
                "baseline_summary": {"variation_percent": 1.0},
                "candidate_summary": {"variation_percent": 20.0},
            },
            {"valid": True, "improvement_percent": 50.0},
        )
        noise_false_accepts += 1
    except DecisionError:
        pass

    try:
        service._validate_acceptance_thresholds(
            {
                "baseline_summary": {"variation_percent": 1.0},
                "candidate_summary": {"variation_percent": 2.0},
            },
            {"valid": True, "improvement_percent": 5.0},
        )
        minimal_gain_detections += 1
    except DecisionError:
        pass

    return noise_false_accepts, minimal_gain_detections


def run_release_probe(root: str | Path) -> ProbeMetrics:
    return asyncio.run(collect_release_evidence(root))


