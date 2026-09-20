"""Benchmark sample, summary, and comparison types."""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Mapping, Sequence
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
    robust_variation_percent: float = 0.0
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
class InputComparison:
    """Baseline and candidate medians for one benchmark input."""

    input_id: str
    baseline_median: float
    candidate_median: float
    improvement_percent: float
    size: int | None = None


@dataclass(frozen=True, slots=True)
class GrowthEstimate:
    """Least-squares slope of ``log(value)`` against ``log(size)``.

    The exponent approximates the asymptotic growth rate, so a drop between
    baseline and candidate is evidence of an algorithmic improvement even when
    the candidate is slower on the smallest input.
    """

    exponent: float
    points: int
    r_squared: float = 0.0


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
    direction: str = "minimize"
    pairing: str = "independent"
    quality_warnings: tuple[str, ...] = ()
    per_input: tuple[InputComparison, ...] = ()
    growth_baseline: float | None = None
    growth_candidate: float | None = None
    growth_delta: float | None = None
    growth_points: int = 0


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
    mad = statistics.median(abs(value - median) for value in values)
    robust_variation = (1.4826 * mad / median * 100.0) if median else 0.0
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
        robust_variation_percent=robust_variation,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        sample_stddev=sample_stddev,
        trimmed_median=statistics.median(trimmed),
        trimmed_count=len(trimmed),
    )


def summarize_by_input(
    samples: Sequence[BenchmarkSample],
    *,
    metric: BenchmarkMetric,
) -> dict[str, list[float]]:
    """Measured values grouped by benchmark input id."""

    grouped: dict[str, list[float]] = {}
    for sample in samples:
        if sample.phase != "measured" or sample.metric is not metric or not sample.valid:
            continue
        grouped.setdefault(sample.input_id, []).append(sample.value)
    return grouped


def estimate_growth(points: Sequence[tuple[int, float]]) -> GrowthEstimate | None:
    """Fit ``log(value) = exponent * log(size) + intercept`` by least squares."""

    usable = [(float(size), float(value)) for size, value in points if size > 1 and value > 0]
    if len(usable) < 2:
        return None
    xs = [math.log(size) for size, _value in usable]
    ys = [math.log(value) for _size, value in usable]
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        return None
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / denominator
    intercept = mean_y - slope * mean_x
    total = sum((y - mean_y) ** 2 for y in ys)
    residual = sum(
        (y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys, strict=True)
    )
    r_squared = 1.0 - residual / total if total > 0 else 0.0
    return GrowthEstimate(exponent=slope, points=len(usable), r_squared=r_squared)


def _improvement_percent(
    baseline_median: float,
    candidate_median: float,
    direction: str,
) -> float | None:
    if baseline_median == 0:
        return None
    if direction == "minimize":
        return (baseline_median - candidate_median) / baseline_median * 100.0
    return (candidate_median - baseline_median) / baseline_median * 100.0


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
    baseline_groups: Mapping[str, Sequence[float]] | None = None,
    candidate_groups: Mapping[str, Sequence[float]] | None = None,
    paired_groups: Mapping[str, Sequence[tuple[float, float]]] | None = None,
    input_sizes: Mapping[str, int] | None = None,
) -> ComparisonResult:
    """Compare two sample sets, optionally across several benchmark inputs.

    With grouped samples the reported improvement is the median of the
    per-input improvements, the variation is the worst per-input variation, and
    the growth exponent is fitted across the input sizes. Without groups the
    whole set is treated as one input, which reproduces the flat behaviour.
    """
    groups_baseline = dict(baseline_groups) if baseline_groups else {"": list(baseline_values)}
    groups_candidate = (
        dict(candidate_groups) if candidate_groups else {"": list(candidate_values)}
    )
    if paired_groups:
        pairings = {key: list(values) for key, values in paired_groups.items()}
    else:
        pairings = {}
        for input_id, baseline_sample in groups_baseline.items():
            candidate_sample = groups_candidate.get(input_id)
            if candidate_sample and len(baseline_sample) == len(candidate_sample):
                pairings[input_id] = list(zip(baseline_sample, candidate_sample, strict=True))
    sizes = dict(input_sizes or {})

    per_input: list[InputComparison] = []
    improvements: list[float] = []
    raw_variations: list[float] = []
    robust_variations: list[float] = []
    p_values: list[float] = []
    paired_relative_improvements: list[float] = []
    for input_id, baseline_sample in groups_baseline.items():
        candidate_sample = groups_candidate.get(input_id)
        if not baseline_sample or not candidate_sample:
            continue
        baseline_summary = summarize_values(list(baseline_sample))
        candidate_summary = summarize_values(list(candidate_sample))
        pairs = pairings.get(input_id)
        if pairs:
            pair_improvements = [
                value
                for baseline_value, candidate_value in pairs
                if (
                    value := _improvement_percent(
                        baseline_value, candidate_value, direction
                    )
                )
                is not None
            ]
            if not pair_improvements:
                continue
            improvement = statistics.median(pair_improvements)
            sample_p, _sample_ci_lower, _sample_ci_upper = _paired_permutation_evidence(
                pairs,
                direction=direction,
                confidence_level=confidence_level,
                rng_seed=rng_seed,
            )
            paired_relative_improvements.extend(pair_improvements)
        else:
            improvement = _improvement_percent(
                baseline_summary.median,
                candidate_summary.median,
                direction,
            )
            if improvement is None:
                continue
            sample_p, _lower, _upper = _permutation_evidence(
                list(baseline_sample),
                list(candidate_sample),
                confidence_level=confidence_level,
                rng_seed=rng_seed,
            )
        per_input.append(
            InputComparison(
                input_id=input_id,
                baseline_median=baseline_summary.median,
                candidate_median=candidate_summary.median,
                improvement_percent=improvement,
                size=sizes.get(input_id),
            )
        )
        improvements.append(improvement)
        raw_variations.append(
            max(baseline_summary.variation_percent, candidate_summary.variation_percent)
        )
        robust_variations.append(
            max(
                baseline_summary.robust_variation_percent,
                candidate_summary.robust_variation_percent,
            )
        )
        p_values.append(sample_p)

    if not per_input:
        return ComparisonResult(
            baseline_run_id=baseline_run_id,
            candidate_run_id=candidate_run_id,
            baseline_id=baseline_id,
            candidate_id=candidate_id,
            comparison_key=comparison_key,
            baseline_median=0.0,
            candidate_median=0.0,
            improvement_percent=0.0,
            valid=False,
            reason="no comparable measured samples",
            direction=direction,
            pairing="independent",
        )

    if paired_relative_improvements:
        ci_lower, ci_upper = _bootstrap_percent_ci(
            paired_relative_improvements,
            confidence_level=confidence_level,
            rng_seed=rng_seed,
        )
    else:
        _flat_p, ci_lower, ci_upper = _permutation_evidence(
            list(baseline_values),
            list(candidate_values),
            confidence_level=confidence_level,
            rng_seed=rng_seed,
        )
    p_value = max(p_values)
    valid = True
    reason = ""
    quality_warnings: list[str] = []
    max_raw_variation = max(raw_variations)
    max_robust_variation = max(robust_variations)
    if max_variation_percent is not None:
        if max_robust_variation > max_variation_percent:
            valid = False
            reason = "robust sample variation exceeds configured threshold"
        elif max_raw_variation > max_variation_percent:
            quality_warnings.append(
                "raw sample variation exceeded configured threshold; "
                "robust variation stayed within it"
            )

    growth_baseline = estimate_growth(
        [(point.size, point.baseline_median) for point in per_input if point.size]
    )
    growth_candidate = estimate_growth(
        [(point.size, point.candidate_median) for point in per_input if point.size]
    )
    growth_delta: float | None = None
    growth_points = 0
    if growth_baseline is not None and growth_candidate is not None:
        growth_delta = growth_baseline.exponent - growth_candidate.exponent
        growth_points = min(growth_baseline.points, growth_candidate.points)

    return ComparisonResult(
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        baseline_id=baseline_id,
        candidate_id=candidate_id,
        comparison_key=comparison_key,
        baseline_median=statistics.median(point.baseline_median for point in per_input),
        candidate_median=statistics.median(point.candidate_median for point in per_input),
        improvement_percent=statistics.median(improvements),
        valid=valid,
        reason=reason,
        p_value=p_value,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        statistically_significant=p_value <= (1.0 - confidence_level),
        direction=direction,
        pairing="paired" if paired_relative_improvements else "independent",
        quality_warnings=tuple(quality_warnings),
        per_input=tuple(per_input),
        growth_baseline=growth_baseline.exponent if growth_baseline else None,
        growth_candidate=growth_candidate.exponent if growth_candidate else None,
        growth_delta=growth_delta,
        growth_points=growth_points,
    )


def _paired_permutation_evidence(
    pairs: Sequence[tuple[float, float]],
    *,
    direction: str,
    confidence_level: float,
    rng_seed: int,
    permutations: int = 2000,
) -> tuple[float, float, float]:
    benefits = [
        benefit
        for baseline_value, candidate_value in pairs
        if (
            benefit := _improvement_percent(baseline_value, candidate_value, direction)
        )
        is not None
    ]
    if not benefits:
        return 1.0, 0.0, 0.0
    observed = statistics.median(benefits)
    rng = random.Random(rng_seed)
    extreme = 0
    for _ in range(permutations):
        statistic = statistics.median(
            benefit if rng.random() >= 0.5 else -benefit for benefit in benefits
        )
        if abs(statistic) >= abs(observed):
            extreme += 1
    p_value = (extreme + 1) / (permutations + 1)
    ci_lower, ci_upper = _bootstrap_percent_ci(
        benefits,
        confidence_level=confidence_level,
        rng_seed=rng_seed,
        samples=permutations,
    )
    return p_value, ci_lower, ci_upper


def _bootstrap_percent_ci(
    values: Sequence[float],
    *,
    confidence_level: float,
    rng_seed: int,
    samples: int = 2000,
) -> tuple[float, float]:
    population = list(values)
    rng = random.Random(rng_seed)
    estimates = sorted(
        statistics.median(population[rng.randrange(len(population))] for _ in population)
        for _ in range(samples)
    )
    tail = (1.0 - confidence_level) / 2.0
    lower = max(0, int(tail * samples) - 1)
    upper = min(samples - 1, int((1.0 - tail) * samples) - 1)
    return estimates[lower], estimates[upper]


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
            baseline.robust_variation_percent > max_variation_percent
            or candidate.robust_variation_percent > max_variation_percent
        ):
            valid = False
            reason = "robust sample variation exceeds configured threshold"
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
        direction=direction,
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
