"""Explainable multi-signal residual anomaly scoring."""

from decimal import Decimal

from backend.anomaly.residual_models import (
    AnomalySeverity,
    DistributionShiftMetrics,
    ResidualAnomalyScore,
    ResidualDistributionStatistics,
    TemporalMetrics,
)


class ResidualAnomalyScorer:
    """Combine distribution and temporal signals without a single amount cutoff."""

    def score(
        self,
        current_statistics: ResidualDistributionStatistics,
        distribution_metrics: DistributionShiftMetrics,
        temporal_metrics: TemporalMetrics,
        *,
        baseline_statistics: ResidualDistributionStatistics | None = None,
    ) -> ResidualAnomalyScore:
        signals: list[str] = []
        if baseline_statistics and baseline_statistics.count:
            mean_gap = abs(current_statistics.mean - baseline_statistics.mean)
            scale = max(
                baseline_statistics.standard_deviation,
                baseline_statistics.absolute_mean,
                Decimal("0.000001"),
            )
            if mean_gap / scale > Decimal("1"):
                signals.append("mean residual shifted materially")
            if (
                current_statistics.standard_deviation
                > baseline_statistics.standard_deviation * Decimal("1.5")
            ):
                signals.append("residual variance increased")
            if (
                current_statistics.zero_residual_ratio
                < baseline_statistics.zero_residual_ratio - Decimal("0.20")
            ):
                signals.append("zero-residual ratio decreased")
            if distribution_metrics.ks_statistic > Decimal("0.20"):
                signals.append("KS distribution shift detected")
            distance_scale = max(
                baseline_statistics.absolute_mean
                + baseline_statistics.standard_deviation,
                Decimal("0.000001"),
            )
            if distribution_metrics.wasserstein_distance / distance_scale > Decimal("1"):
                signals.append("Wasserstein distance increased")
            if distribution_metrics.population_stability_index > Decimal("0.10"):
                signals.append("PSI distribution shift detected")

        if temporal_metrics.cusum_change_detected:
            signals.append("CUSUM change detected")
        if current_statistics.count and (
            current_statistics.positive_ratio >= Decimal("0.75")
            or current_statistics.negative_ratio >= Decimal("0.75")
        ):
            signals.append("persistent residual direction bias")

        signal_count = Decimal(len(signals))
        score = min(Decimal("100"), signal_count / Decimal("8") * Decimal("100"))
        if score >= Decimal("75"):
            severity = AnomalySeverity.CRITICAL
        elif score >= Decimal("50"):
            severity = AnomalySeverity.ANOMALOUS
        elif score >= Decimal("25"):
            severity = AnomalySeverity.WATCH
        else:
            severity = AnomalySeverity.NORMAL

        explanation = (
            "No material residual behavior signals detected."
            if not signals
            else "Score combines: " + "; ".join(signals) + "."
        )
        return ResidualAnomalyScore(
            score=score,
            severity=severity,
            signals=signals,
            distribution_metrics=distribution_metrics,
            temporal_metrics=temporal_metrics,
            explanation=explanation,
        )