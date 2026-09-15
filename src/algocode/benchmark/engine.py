"""Language-independent benchmark sampling engine."""

from __future__ import annotations

from pathlib import Path

from algocode.benchmark.environment import compute_environment_hash
from algocode.benchmark.spec import (
    BenchmarkSpec,
    compute_benchmark_spec_hash,
    compute_comparison_key,
    compute_input_hash,
)
from algocode.benchmark.types import BenchmarkResult, BenchmarkSample, summarize_samples
from algocode.domain.model import BenchmarkMetric, BenchmarkScope
from algocode.sandbox.runner import SandboxProcessRunner


async def collect_target_samples(
    workspace: Path,
    spec: BenchmarkSpec,
    *,
    target_kind: str,
    target_id: str,
    sandbox_runner: SandboxProcessRunner | None = None,
) -> tuple[BenchmarkSample, ...]:
    """Collect warmup and measured samples for one target."""

    samples: list[BenchmarkSample] = []
    for index in range(spec.warmup):
        samples.append(
            await run_sample(
                workspace,
                spec,
                target_kind=target_kind,
                target_id=target_id,
                phase="warmup",
                index=index,
                sandbox_runner=sandbox_runner,
            )
        )
    for index in range(spec.repeats):
        samples.append(
            await run_sample(
                workspace,
                spec,
                target_kind=target_kind,
                target_id=target_id,
                phase="measured",
                index=index,
                sandbox_runner=sandbox_runner,
            )
        )
    return tuple(samples)


async def run_benchmark_process(
    workspace: Path,
    spec: BenchmarkSpec,
    *,
    target_kind: str = "target",
    target_id: str = "target",
    sandbox_runner: SandboxProcessRunner | None = None,
) -> BenchmarkResult:
    samples = await collect_target_samples(
        workspace,
        spec,
        target_kind=target_kind,
        target_id=target_id,
        sandbox_runner=sandbox_runner,
    )
    summary = summarize_samples(samples, metric=spec.metric)
    measured = [sample for sample in samples if sample.phase == "measured"]
    valid = summary is not None and all(sample.valid for sample in measured)
    spec_hash = compute_benchmark_spec_hash(spec)
    input_hash = compute_input_hash(spec)
    environment_hash = compute_environment_hash(workspace)
    comparison_key = compute_comparison_key(
        spec_hash=spec_hash,
        input_hash=input_hash,
        environment_hash=environment_hash,
    )
    return BenchmarkResult(
        target_kind=target_kind,
        target_id=target_id,
        workspace_ref=str(workspace),
        spec_hash=spec_hash,
        input_hash=input_hash,
        environment_hash=environment_hash,
        comparison_key=comparison_key,
        workspace_hash="",
        samples=samples,
        summary=summary,
        valid=valid,
        message="" if valid else "one or more measured samples were invalid",
    )


async def collect_interleaved_samples(
    baseline_workspace: Path,
    candidate_workspace: Path,
    baseline_spec: BenchmarkSpec,
    candidate_spec: BenchmarkSpec,
    *,
    baseline_id: str,
    candidate_id: str,
    sandbox_runner: SandboxProcessRunner | None = None,
) -> tuple[BenchmarkSample, ...]:
    """Collect warmups then alternate Baseline/Candidate measurements."""

    samples: list[BenchmarkSample] = []
    for index in range(baseline_spec.warmup):
        samples.append(
            await run_sample(
                baseline_workspace,
                baseline_spec,
                target_kind="baseline",
                target_id=baseline_id,
                phase="warmup",
                index=index,
                sandbox_runner=sandbox_runner,
            )
        )
        samples.append(
            await run_sample(
                candidate_workspace,
                candidate_spec,
                target_kind="candidate",
                target_id=candidate_id,
                phase="warmup",
                index=index,
                sandbox_runner=sandbox_runner,
            )
        )
    for index in range(baseline_spec.repeats):
        order = (
            ("baseline", baseline_workspace, baseline_id),
            ("candidate", candidate_workspace, candidate_id),
        )
        if index % 2:
            order = tuple(reversed(order))
        for target_kind, workspace, target_id in order:
            target_spec = baseline_spec if target_kind == "baseline" else candidate_spec
            samples.append(
                await run_sample(
                    workspace,
                    target_spec,
                    target_kind=target_kind,
                    target_id=target_id,
                    phase="measured",
                    index=index,
                    sandbox_runner=sandbox_runner,
                )
            )
    return tuple(samples)


async def run_sample(
    workspace: Path,
    spec: BenchmarkSpec,
    *,
    target_kind: str,
    target_id: str,
    phase: str,
    index: int,
    sandbox_runner: SandboxProcessRunner | None = None,
) -> BenchmarkSample:
    if spec.metric is not BenchmarkMetric.WALL_TIME:
        return BenchmarkSample(
            target_kind=target_kind,
            target_id=target_id,
            phase=phase,
            index=index,
            metric=spec.metric,
            value=0.0,
            duration_seconds=0.0,
            exit_code=1,
            valid=False,
            message=f"{spec.metric.value} is not implemented in M4",
        )
    command = tuple(token.format(workspace=workspace) for token in spec.run_command)
    input_bytes = spec.input.encode() if spec.scope is BenchmarkScope.STDIN else b""
    runner = sandbox_runner or SandboxProcessRunner()
    result = await runner.run(
        command,
        cwd=workspace,
        timeout_seconds=spec.timeout_seconds,
        input_bytes=input_bytes,
    )
    if result.start_failed or result.timed_out or result.exit_code != 0:
        return BenchmarkSample(
            target_kind=target_kind,
            target_id=target_id,
            phase=phase,
            index=index,
            metric=spec.metric,
            value=0.0,
            duration_seconds=result.duration_seconds,
            exit_code=result.exit_code,
            valid=False,
            message=result.stderr.decode(errors="replace"),
        )
    return BenchmarkSample(
        target_kind=target_kind,
        target_id=target_id,
        phase=phase,
        index=index,
        metric=spec.metric,
        value=result.duration_seconds,
        duration_seconds=result.duration_seconds,
        exit_code=result.exit_code,
        valid=True,
        message="",
    )
