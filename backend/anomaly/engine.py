"""Cross-domain residual distribution intelligence orchestration."""

from collections.abc import Sequence
from decimal import Decimal

from backend.anomaly.distribution import (
    ResidualDistributionAnalyzer,
    ensure_single_currency,
)
from backend.anomaly.drift import TemporalDriftAnalyzer
from backend.anomaly.residual_models import (
    ResidualAnalysis,
    ResidualBaseline,
    ResidualObservation,
)
from backend.anomaly.scoring import ResidualAnomalyScorer


class ResidualIntelligenceEngine:
    """Analyze residual behavior independently of financial-control domains."""

    def __init__(self) -> None:
        self.distribution = ResidualDistributionAnalyzer()
        self.temporal = TemporalDriftAnalyzer()
        self.scorer = ResidualAnomalyScorer()

    def analyze(
        self,
        current: Sequence[ResidualObservation],
        *,
        baseline: ResidualBaseline | None = None,
        baseline_residuals: Sequence[ResidualObservation] | None = None,
        rolling_window: int = 5,
        currency: str | None = None,
    ) -> ResidualAnalysis:
        current_currency = ensure_single_currency(current, currency)
        baseline_population = list(baseline_residuals or [])
        if baseline:
            if baseline.sample_residuals:
                distribution_baseline: list[Decimal] = baseline.sample_residuals
            else:
                distribution_baseline = []
            baseline_statistics = baseline.statistics
            if current_currency and current_currency != baseline.currency:
                raise ValueError("baseline and current currencies must match")
        else:
            distribution_baseline = baseline_population
            baseline_statistics = (
                self.distribution.analyze(baseline_population)
                if baseline_population
                else None
            )
            if baseline_population:
                ensure_single_currency(baseline_population, current_currency)

        current_statistics = self.distribution.analyze(current)
        distribution_shift = self.distribution.compare(
            distribution_baseline,
            current,
        )
        temporal_metrics = self.temporal.analyze(
            current,
            baseline_statistics=baseline_statistics,
            rolling_window=rolling_window,
        )
        anomaly_score = self.scorer.score(
            current_statistics,
            distribution_shift,
            temporal_metrics,
            baseline_statistics=baseline_statistics,
        )
        return ResidualAnalysis(
            distribution_statistics=current_statistics,
            distribution_shift=distribution_shift,
            temporal_metrics=temporal_metrics,
            anomaly_score=anomaly_score,
        )