"""Temporal residual drift analysis with rolling statistics and CUSUM."""

from collections.abc import Sequence
from decimal import Decimal

from backend.anomaly.residual_models import (
    ResidualDistributionStatistics,
    ResidualObservation,
    TemporalMetrics,
)


class TemporalDriftAnalyzer:
    """Calculate rolling residual behavior and a deterministic CUSUM signal."""

    def analyze(
        self,
        residuals: Sequence[ResidualObservation],
        *,
        baseline_statistics: ResidualDistributionStatistics | None = None,
        rolling_window: int = 5,
        cusum_threshold: Decimal | None = None,
    ) -> TemporalMetrics:
        if rolling_window < 1:
            raise ValueError("rolling_window must be at least 1")

        ordered = sorted(residuals, key=lambda observation: observation.timestamp)
        amounts = [observation.residual_amount for observation in ordered]
        rolling_mean: list[Decimal] = []
        rolling_absolute_mean: list[Decimal] = []
        rolling_zero_ratio: list[Decimal] = []
        for index in range(len(amounts)):
            window = amounts[max(0, index - rolling_window + 1) : index + 1]
            count = Decimal(len(window))
            rolling_mean.append(sum(window, Decimal("0")) / count)
            rolling_absolute_mean.append(
                sum((abs(value) for value in window), Decimal("0")) / count
            )
            rolling_zero_ratio.append(
                Decimal(sum(value == Decimal("0") for value in window)) / count
            )

        target = baseline_statistics.mean if baseline_statistics else Decimal("0")
        positive = Decimal("0")
        negative = Decimal("0")
        max_absolute = Decimal("0")
        for amount in amounts:
            deviation = amount - target
            positive = max(Decimal("0"), positive + deviation)
            negative = min(Decimal("0"), negative + deviation)
            max_absolute = max(max_absolute, abs(positive), abs(negative))

        if cusum_threshold is None:
            scale = (
                baseline_statistics.standard_deviation
                if baseline_statistics
                else Decimal("0")
            )
            cusum_threshold = max(scale * Decimal("5"), Decimal("0.01"))

        return TemporalMetrics(
            rolling_window=rolling_window,
            rolling_mean=rolling_mean,
            rolling_absolute_mean=rolling_absolute_mean,
            rolling_zero_residual_ratio=rolling_zero_ratio,
            cusum_positive=positive,
            cusum_negative=negative,
            cusum_max_absolute=max_absolute,
            cusum_change_detected=max_absolute > cusum_threshold,
        )