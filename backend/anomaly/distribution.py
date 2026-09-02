"""Deterministic residual population and distribution-shift analysis."""

from bisect import bisect_right
from collections.abc import Iterable, Sequence
from decimal import Decimal, getcontext

from backend.anomaly.residual_models import (
    DistributionShiftMetrics,
    ResidualDistributionStatistics,
    ResidualObservation,
)

ZERO = Decimal("0")
ONE = Decimal("1")
EPSILON = Decimal("0.000001")


class ResidualDistributionAnalyzer:
    """Calculate population statistics and distribution-shift indicators."""

    def analyze(
        self, residuals: Iterable[ResidualObservation | Decimal]
    ) -> ResidualDistributionStatistics:
        values = _amounts(residuals)
        count = len(values)
        if count == 0:
            return ResidualDistributionStatistics(
                count=0,
                zero_residual_ratio=ZERO,
                mean=ZERO,
                median=ZERO,
                standard_deviation=ZERO,
                p95=ZERO,
                p99=ZERO,
                absolute_mean=ZERO,
                absolute_median=ZERO,
                positive_ratio=ZERO,
                negative_ratio=ZERO,
            )

        ordered = sorted(values)
        absolute_values = sorted(abs(value) for value in values)
        count_decimal = Decimal(count)
        mean = sum(values, ZERO) / count_decimal
        return ResidualDistributionStatistics(
            count=count,
            zero_residual_ratio=Decimal(sum(value == ZERO for value in values)) / count_decimal,
            mean=mean,
            median=_percentile(ordered, Decimal("0.50")),
            standard_deviation=_standard_deviation(values, mean),
            minimum=ordered[0],
            maximum=ordered[-1],
            p95=_percentile(ordered, Decimal("0.95")),
            p99=_percentile(ordered, Decimal("0.99")),
            absolute_mean=sum((abs(value) for value in values), ZERO) / count_decimal,
            absolute_median=_percentile(absolute_values, Decimal("0.50")),
            positive_ratio=Decimal(sum(value > ZERO for value in values)) / count_decimal,
            negative_ratio=Decimal(sum(value < ZERO for value in values)) / count_decimal,
        )

    def compare(
        self,
        baseline: Iterable[ResidualObservation | Decimal],
        current: Iterable[ResidualObservation | Decimal],
    ) -> DistributionShiftMetrics:
        """Compare two empirical one-dimensional residual distributions."""

        baseline_values = sorted(_amounts(baseline))
        current_values = sorted(_amounts(current))
        return DistributionShiftMetrics(
            baseline_count=len(baseline_values),
            current_count=len(current_values),
            ks_statistic=_kolmogorov_smirnov(baseline_values, current_values),
            wasserstein_distance=_wasserstein_distance(
                baseline_values, current_values
            ),
            population_stability_index=_population_stability_index(
                baseline_values, current_values
            ),
        )


def ensure_single_currency(
    residuals: Sequence[ResidualObservation], currency: str | None = None
) -> str | None:
    """Reject mixed-currency populations rather than aggregating them."""

    currencies = {observation.currency for observation in residuals}
    if currency is not None:
        currencies.add(currency)
    if len(currencies) > 1:
        raise ValueError(
            "multiple currencies cannot be analyzed together: "
            + ", ".join(sorted(currencies))
        )
    return next(iter(currencies), currency)


def _amounts(
    residuals: Iterable[ResidualObservation | Decimal],
) -> list[Decimal]:
    return [
        value.residual_amount if isinstance(value, ResidualObservation) else value
        for value in residuals
    ]


def _percentile(values: Sequence[Decimal], percentile: Decimal) -> Decimal:
    if not values:
        return ZERO
    if len(values) == 1:
        return values[0]
    position = Decimal(len(values) - 1) * percentile
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(values) - 1)
    fraction = position - Decimal(lower_index)
    return values[lower_index] + (
        values[upper_index] - values[lower_index]
    ) * fraction


def _standard_deviation(values: Sequence[Decimal], mean: Decimal) -> Decimal:
    variance = sum(((value - mean) ** 2 for value in values), ZERO) / Decimal(
        len(values)
    )
    return variance.sqrt()


def _kolmogorov_smirnov(
    baseline: Sequence[Decimal], current: Sequence[Decimal]
) -> Decimal:
    if not baseline or not current:
        return ZERO
    points = sorted(set(baseline) | set(current))
    baseline_count = Decimal(len(baseline))
    current_count = Decimal(len(current))
    maximum = ZERO
    for point in points:
        baseline_cdf = Decimal(bisect_right(baseline, point)) / baseline_count
        current_cdf = Decimal(bisect_right(current, point)) / current_count
        maximum = max(maximum, abs(baseline_cdf - current_cdf))
    return maximum


def _wasserstein_distance(
    baseline: Sequence[Decimal], current: Sequence[Decimal]
) -> Decimal:
    if not baseline or not current:
        return ZERO
    points = sorted(set(baseline) | set(current))
    baseline_count = Decimal(len(baseline))
    current_count = Decimal(len(current))
    distance = ZERO
    for left, right in zip(points, points[1:]):
        baseline_cdf = Decimal(bisect_right(baseline, left)) / baseline_count
        current_cdf = Decimal(bisect_right(current, left)) / current_count
        distance += abs(baseline_cdf - current_cdf) * (right - left)
    return distance


def _population_stability_index(
    baseline: Sequence[Decimal], current: Sequence[Decimal]
) -> Decimal:
    if not baseline or not current:
        return ZERO
    points = sorted(set(baseline) | set(current))
    baseline_count = Decimal(len(baseline))
    current_count = Decimal(len(current))
    psi = ZERO
    for point in points:
        baseline_proportion = (
            Decimal(baseline.count(point)) / baseline_count + EPSILON
        )
        current_proportion = Decimal(current.count(point)) / current_count + EPSILON
        psi += (current_proportion - baseline_proportion) * (
            current_proportion / baseline_proportion
        ).ln()
    return max(psi, ZERO)