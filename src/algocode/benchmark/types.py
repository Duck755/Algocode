"""Benchmark sample, summary, and comparison types."""

from __future__ import annotations

import random
import statistics
from collections.abc import Sequence
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
    input_id: str = ""


@dataclass(frozen=True, slots=True)
class BenchmarkSummary:
    count: int
    median: float
    minimum: float
    maximum: float
    mean: float
    stddev: float
    variation_percent: float
    ci_lower: float = 0.0
    ci_upper: float = 0.0
    sample_stddev: float = 0.0
    trimmed_median: float = 0.0
    trimmed_count: int = 0


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
    p_value: float = 1.0
    ci_lower: float = 0.0
    ci_upper: float = 0.0
    statistically_significant: bool = False


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
    return summarize_values(values)


def summarize_values(values: Sequence[float]) -> BenchmarkSummary:
    median = statistics.median(values)
    mean = statistics.fmean(values)
    stddev = statistics.pstdev(values)
    sample_stddev = statistics.stdev(values) if len(values) > 1 else 0.0
    variation = (stddev / median * 100.0) if median else 0.0
    ci_lower, ci_upper = _bootstrap_ci(values)
    trimmed = _iqr_trimmed(values)
    return BenchmarkSummary(
        count=len(values),
        median=median,
        minimum=min(values),
        maximum=max(values),
        mean=mean,
        stddev=stddev,
        variation_percent=variation,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        sample_stddev=sample_stddev,
        trimmed_median=statistics.median(trimmed),
        trimmed_count=len(trimmed),
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
    return _compare_summary_stats(
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        baseline_id=baseline_id,
        candidate_id=candidate_id,
        comparison_key=comparison_key,
        baseline=baseline,
        candidate=candidate,
        direction=direction,
        max_variation_percent=max_variation_percent,
    )


def compare_sample_sets(
    *,
    baseline_run_id: str,
    candidate_run_id: str,
    baseline_id: str,
    candidate_id: str,
    comparison_key: str,
    baseline_values: Sequence[float],
    candidate_values: Sequence[float],
    direction: str,
    max_variation_percent: float | None,
    confidence_level: float = 0.95,
    rng_seed: int = 0,
) -> ComparisonResult:
    baseline = summarize_values(baseline_values)
    candidate = summarize_values(candidate_values)
    comparison = _compare_summary_stats(
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        baseline_id=baseline_id,
        candidate_id=candidate_id,
        comparison_key=comparison_key,
        baseline=baseline,
        candidate=candidate,
        direction=direction,
        max_variation_percent=max_variation_percent,
    )
    p_value, ci_lower, ci_upper = _permutation_evidence(
        baseline_values,
        candidate_values,
        confidence_level=confidence_level,
        rng_seed=rng_seed,
    )
    return ComparisonResult(
        baseline_run_id=comparison.baseline_run_id,
        candidate_run_id=comparison.candidate_run_id,
        baseline_id=comparison.baseline_id,
        candidate_id=comparison.candidate_id,
        comparison_key=comparison.comparison_key,
        baseline_median=comparison.baseline_median,
        candidate_median=comparison.candidate_median,
        improvement_percent=comparison.improvement_percent,
        valid=comparison.valid,
        reason=comparison.reason,
        p_value=p_value,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        statistically_significant=p_value <= (1.0 - confidence_level),
    )


def _compare_summary_stats(
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
    if baseline.median == 0:
        improvement = 0.0
        valid = False
        reason = "baseline median is zero"
    else:
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


def _bootstrap_ci(
    values: Sequence[float],
    *,
    confidence_level: float = 0.95,
    samples: int = 2000,
    rng_seed: int = 0,
) -> tuple[float, float]:
    rng = random.Random(rng_seed)
    population = list(values)
    estimates = sorted(
        statistics.median(population[rng.randrange(len(population))] for _ in population)
        for _ in range(samples)
    )
    tail = (1.0 - confidence_level) / 2.0
    lower = max(0, int(tail * samples) - 1)
    upper = min(samples - 1, int((1.0 - tail) * samples) - 1)
    return estimates[lower], estimates[upper]


def _iqr_trimmed(values: Sequence[float]) -> list[float]:
    ordered = sorted(values)
    if len(ordered) < 4:
        return list(values)
    q1 = statistics.median(ordered[: len(ordered) // 2])
    q3 = statistics.median(ordered[(len(ordered) + 1) // 2 :])
    iqr = q3 - q1
    if iqr == 0:
        return list(values)
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return [value for value in values if lower <= value <= upper] or list(values)


def _permutation_evidence(
    baseline_values: Sequence[float],
    candidate_values: Sequence[float],
    *,
    confidence_level: float,
    rng_seed: int,
    permutations: int = 2000,
) -> tuple[float, float, float]:
    baseline = list(baseline_values)
    candidate = list(candidate_values)
    if not baseline or not candidate:
        return 1.0, 0.0, 0.0
    observed = statistics.median(candidate) - statistics.median(baseline)
    pooled = baseline + candidate
    rng = random.Random(rng_seed)
    baseline_size = len(baseline)
    extreme = 0
    for _ in range(permutations):
        shuffled = pooled[:]
        rng.shuffle(shuffled)
        statistic = statistics.median(shuffled[baseline_size:]) - statistics.median(
            shuffled[:baseline_size]
        )
        if abs(statistic) >= abs(observed):
            extreme += 1
    p_value = (extreme + 1) / (permutations + 1)

    bootstrap_differences = sorted(
        statistics.median(
            candidate[rng.randrange(len(candidate))] for _ in candidate
        )
        - statistics.median(
            baseline[rng.randrange(len(baseline))] for _ in baseline
        )
        for _ in range(permutations)
    )
    tail = (1.0 - confidence_level) / 2.0
    lower = bootstrap_differences[max(0, int(tail * permutations) - 1)]
    upper = bootstrap_differences[min(permutations - 1, int((1.0 - tail) * permutations) - 1)]
    return p_value, lower, upper
