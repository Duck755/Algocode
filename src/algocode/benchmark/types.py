"""Benchmark sample, summary, and comparison types."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from algocode.domain.model import BenchmarkMetric


@dataclass(frozen=True, slots=True)
class BenchmarkSample:
    target_kind: str
    target_id: str
    phase: str
    index: int
    metric: BenchmarkMetric
    value: float
    duration_seconds: float
    exit_code: int
    valid: bool = True
    message: str = ""


@dataclass(frozen=True, slots=True)
class BenchmarkSummary:
    count: int
    median: float
    minimum: float
    maximum: float
    mean: float
    stddev: float
    variation_percent: float


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    target_kind: str
    target_id: str
    workspace_ref: str
    spec_hash: str
    input_hash: str
    environment_hash: str
    comparison_key: str
    workspace_hash: str
    samples: tuple[BenchmarkSample, ...] = field(default_factory=tuple)
    summary: BenchmarkSummary | None = None
    valid: bool = False
    message: str = ""


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    baseline_run_id: str
    candidate_run_id: str
    baseline_id: str
    candidate_id: str
    comparison_key: str
    baseline_median: float
    candidate_median: float
    improvement_percent: float
    valid: bool
    reason: str = ""


def summarize_samples(
    samples: tuple[BenchmarkSample, ...],
    *,
    metric: BenchmarkMetric,
) -> BenchmarkSummary | None:
    values = [
        sample.value
        for sample in samples
        if sample.phase == "measured" and sample.metric is metric and sample.valid
    ]
    if not values:
        return None
    median = statistics.median(values)
    mean = statistics.fmean(values)
    variation = (statistics.pstdev(values) / median * 100.0) if median else 0.0
    return BenchmarkSummary(
        count=len(values),
        median=median,
        minimum=min(values),
        maximum=max(values),
        mean=mean,
        stddev=statistics.pstdev(values),
        variation_percent=variation,
    )


def compare_summaries(
    *,
    baseline_run_id: str,
    candidate_run_id: str,
    baseline_id: str,
    candidate_id: str,
    comparison_key: str,
    baseline: BenchmarkSummary,
    candidate: BenchmarkSummary,
    direction: str,
    max_variation_percent: float | None,
) -> ComparisonResult:
    if direction == "minimize":
        improvement = (baseline.median - candidate.median) / baseline.median * 100.0
    else:
        improvement = (candidate.median - baseline.median) / baseline.median * 100.0
    valid = True
    reason = ""
    if max_variation_percent is not None:
        if (
            baseline.variation_percent > max_variation_percent
            or candidate.variation_percent > max_variation_percent
        ):
            valid = False
            reason = "sample variation exceeds configured threshold"
    return ComparisonResult(
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        baseline_id=baseline_id,
        candidate_id=candidate_id,
        comparison_key=comparison_key,
        baseline_median=baseline.median,
        candidate_median=candidate.median,
        improvement_percent=improvement,
        valid=valid,
        reason=reason,
    )
