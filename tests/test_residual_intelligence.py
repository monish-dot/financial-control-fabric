"""Tests for residual persistence, statistics, drift, scoring, and baselines."""

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.anomaly.baseline import ResidualBaselineManager, ResidualBaselineStore
from backend.anomaly.distribution import ResidualDistributionAnalyzer
from backend.anomaly.drift import TemporalDriftAnalyzer
from backend.anomaly.engine import ResidualIntelligenceEngine
from backend.anomaly.residual_models import (
    AnomalySeverity,
    ResidualObservation,
)
from backend.anomaly.residual_store import ResidualStore
from backend.controls.models import ControlDomain, ControlStatus
from backend.database import Database
from data.residual_scenarios import (
    PERIOD_START,
    build_residual_populations,
)


@pytest.fixture
def residual_store(tmp_path) -> Iterator[ResidualStore]:
    database = Database(tmp_path / "financial_control.db")
    database.initialize()
    yield ResidualStore(database.session_factory)
    database.dispose()


def test_residual_persistence_and_retrieval(residual_store: ResidualStore) -> None:
    observation = _observation(
        "persisted",
        "1.25",
        domain=ControlDomain.NODAL_ESCROW,
    )

    residual_store.record_residual(observation)
    retrieved = residual_store.get_residual("persisted")

    assert retrieved == observation
    assert retrieved is not None
    assert retrieved.residual_amount == Decimal("1.25")
    assert retrieved.vector is None


def test_residual_filtering(residual_store: ResidualStore) -> None:
    residual_store.record_residual(
        _observation(
            "filter-a",
            "1",
            entity_id="entity-a",
            account_id="account-a",
            merchant_id="merchant-a",
        )
    )
    residual_store.record_residual(
        _observation(
            "filter-b",
            "2",
            domain=ControlDomain.SETTLEMENT,
            entity_id="entity-b",
            account_id="account-b",
            merchant_id="merchant-b",
        )
    )

    assert [item.residual_id for item in residual_store.list_residuals_by_domain(
        ControlDomain.SETTLEMENT
    )] == ["filter-b"]
    assert [item.residual_id for item in residual_store.list_residuals_by_entity(
        "entity-b"
    )] == ["filter-b"]
    assert [item.residual_id for item in residual_store.list_residuals_by_account(
        "account-a"
    )] == ["filter-a"]
    assert [item.residual_id for item in residual_store.list_residuals_by_merchant(
        "merchant-b"
    )] == ["filter-b"]
    assert [item.residual_id for item in residual_store.list_residuals_by_period(
        PERIOD_START, PERIOD_START + timedelta(days=1)
    )] == ["filter-a", "filter-b"]


def test_zero_residual_population() -> None:
    statistics = ResidualDistributionAnalyzer().analyze(
        [Decimal("0"), Decimal("0"), Decimal("0")]
    )

    assert statistics.count == 3
    assert statistics.zero_residual_ratio == Decimal("1")
    assert statistics.mean == Decimal("0")
    assert statistics.standard_deviation == Decimal("0")


def test_mean_median_p95_and_p99_calculation() -> None:
    statistics = ResidualDistributionAnalyzer().analyze(
        [Decimal("0"), Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4")]
    )

    assert statistics.mean == Decimal("2")
    assert statistics.median == Decimal("2")
    assert statistics.p95 == Decimal("3.8")
    assert statistics.p99 == Decimal("3.96")


def test_positive_and_negative_bias_detection() -> None:
    statistics = ResidualDistributionAnalyzer().analyze(
        [Decimal("10"), Decimal("11"), Decimal("9"), Decimal("12")]
    )

    assert statistics.positive_ratio == Decimal("1")
    assert statistics.negative_ratio == Decimal("0")
    assert statistics.absolute_mean == statistics.mean


def test_stable_distribution() -> None:
    analyzer = ResidualDistributionAnalyzer()
    stable = [Decimal("0"), Decimal("0"), Decimal("1"), Decimal("-1")]

    metrics = analyzer.compare(stable, stable)

    assert metrics.ks_statistic == Decimal("0")
    assert metrics.wasserstein_distance == Decimal("0")
    assert metrics.population_stability_index == Decimal("0")


def test_variance_increase() -> None:
    analyzer = ResidualDistributionAnalyzer()
    baseline = analyzer.analyze([Decimal("0"), Decimal("1"), Decimal("-1")])
    current = analyzer.analyze(
        [Decimal("0"), Decimal("1"), Decimal("-1"), Decimal("8"), Decimal("-8")]
    )

    assert current.standard_deviation > baseline.standard_deviation


def test_distribution_shift_metrics() -> None:
    analyzer = ResidualDistributionAnalyzer()
    baseline = [Decimal("0"), Decimal("0"), Decimal("1"), Decimal("-1")]
    current = [Decimal("20"), Decimal("25"), Decimal("30"), Decimal("35")]

    metrics = analyzer.compare(baseline, current)

    assert metrics.ks_statistic > Decimal("0")
    assert metrics.wasserstein_distance > Decimal("0")
    assert metrics.population_stability_index > Decimal("0")


def test_temporal_rolling_statistics_and_cusum() -> None:
    observations = [
        _observation(f"temporal-{index}", str(index), timestamp=PERIOD_START + timedelta(days=index))
        for index in range(4)
    ]

    metrics = TemporalDriftAnalyzer().analyze(
        observations,
        rolling_window=2,
        cusum_threshold=Decimal("2"),
    )

    assert metrics.rolling_mean == [
        Decimal("0"),
        Decimal("0.5"),
        Decimal("1.5"),
        Decimal("2.5"),
    ]
    assert metrics.rolling_absolute_mean == metrics.rolling_mean
    assert metrics.cusum_max_absolute == Decimal("6")
    assert metrics.cusum_change_detected is True


def test_anomaly_scoring_and_severity() -> None:
    populations = build_residual_populations()
    engine = ResidualIntelligenceEngine()
    stable = populations["stable"]
    current = populations["persistent_positive_bias"]

    stable_analysis = engine.analyze(stable, baseline_residuals=stable)
    anomalous_analysis = engine.analyze(current, baseline_residuals=stable)

    assert stable_analysis.anomaly_score.severity is AnomalySeverity.NORMAL
    assert anomalous_analysis.anomaly_score.score > stable_analysis.anomaly_score.score
    assert anomalous_analysis.anomaly_score.severity in {
        AnomalySeverity.ANOMALOUS,
        AnomalySeverity.CRITICAL,
    }
    assert anomalous_analysis.anomaly_score.signals


def test_baseline_creation_persistence_and_comparison(tmp_path) -> None:
    database = Database(tmp_path / "financial_control.db")
    database.initialize()
    manager = ResidualBaselineManager(
        ResidualBaselineStore(database.session_factory)
    )
    observations = build_residual_populations()["stable"]

    baseline = manager.create_baseline(
        observations,
        domain=ControlDomain.NODAL_ESCROW,
        entity_id="synthetic-entity",
        account_id="synthetic-account",
        currency="INR",
        window_start=PERIOD_START,
        window_end=PERIOD_START + timedelta(days=7),
    )
    loaded = manager.get_baseline(baseline.baseline_id)
    comparison = manager.compare_to_baseline(
        baseline,
        build_residual_populations()["persistent_positive_bias"],
    )
    database.dispose()

    assert loaded is not None
    assert loaded.sample_count == len(observations)
    assert comparison.distribution_shift.ks_statistic > Decimal("0")


def test_empty_population_handling() -> None:
    analysis = ResidualIntelligenceEngine().analyze([])

    assert analysis.distribution_statistics.count == 0
    assert analysis.distribution_shift.baseline_count == 0
    assert analysis.anomaly_score.severity is AnomalySeverity.NORMAL


def test_multi_domain_support() -> None:
    populations = build_residual_populations()
    engine = ResidualIntelligenceEngine()

    results = [
        engine.analyze(populations[name])
        for name in (
            "domain_nodal_escrow",
            "domain_settlement",
            "domain_merchant_payout",
            "domain_revenue_recognition",
            "domain_cross_entity",
        )
    ]

    assert len(results) == 5
    assert all(result.distribution_statistics.count == 4 for result in results)


def test_multi_currency_isolation() -> None:
    inr = _observation("inr", "1", currency="INR")
    usd = _observation("usd", "1", currency="USD")

    with pytest.raises(ValueError, match="multiple currencies"):
        ResidualIntelligenceEngine().analyze([inr, usd])


def _observation(
    residual_id: str,
    amount: str,
    *,
    domain: ControlDomain = ControlDomain.NODAL_ESCROW,
    entity_id: str = "entity-a",
    account_id: str = "account-a",
    merchant_id: str = "merchant-a",
    currency: str = "INR",
    timestamp: datetime = PERIOD_START,
) -> ResidualObservation:
    decimal_amount = Decimal(amount)
    return ResidualObservation(
        residual_id=residual_id,
        control_id="test-control",
        domain=domain,
        entity_id=entity_id,
        account_id=account_id,
        merchant_id=merchant_id,
        partner_id="partner-a",
        timestamp=timestamp,
        expected_amount=Decimal("0"),
        actual_amount=decimal_amount,
        residual_amount=decimal_amount,
        currency=currency,
        status=ControlStatus.PASS if decimal_amount == 0 else ControlStatus.FAIL,
    )