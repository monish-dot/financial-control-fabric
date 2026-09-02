"""Residual baseline creation, persistence, and comparison."""

import json
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.anomaly.distribution import ResidualDistributionAnalyzer, ensure_single_currency
from backend.anomaly.engine import ResidualIntelligenceEngine
from backend.anomaly.residual_models import (
    ResidualAnalysis,
    ResidualBaseline,
    ResidualDistributionStatistics,
    ResidualObservation,
)
from backend.database.models import ResidualBaselineRecord
from backend.controls.models import ControlDomain


class ResidualBaselineStore:
    """Persist and retrieve residual baselines in a separate SQLite table."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def create_baseline(self, baseline: ResidualBaseline) -> ResidualBaseline:
        with self._session_factory() as session:
            session.add(
                ResidualBaselineRecord(
                    baseline_id=baseline.baseline_id,
                    domain=baseline.domain.value,
                    entity_id=baseline.entity_id,
                    account_id=baseline.account_id,
                    currency=baseline.currency,
                    window_start=baseline.window_start.isoformat(),
                    window_end=baseline.window_end.isoformat(),
                    sample_count=baseline.sample_count,
                    statistics_json=json.dumps(
                        baseline.statistics.model_dump(mode="json"),
                        sort_keys=True,
                    ),
                    created_at=baseline.created_at.isoformat(),
                    sample_residuals_json=json.dumps(
                        [format(value, "f") for value in baseline.sample_residuals]
                    ),
                )
            )
            session.commit()
        return baseline

    def get_baseline(self, baseline_id: str) -> ResidualBaseline | None:
        with self._session_factory() as session:
            record = session.get(ResidualBaselineRecord, baseline_id)
            return _record_to_baseline(record) if record else None

    def get_latest_by_domain(
        self,
        domain: ControlDomain | str,
        *,
        entity_id: str | None = None,
        account_id: str | None = None,
        currency: str | None = None,
    ) -> ResidualBaseline | None:
        value = domain.value if isinstance(domain, ControlDomain) else domain
        with self._session_factory() as session:
            statement = (
                select(ResidualBaselineRecord)
                .where(ResidualBaselineRecord.domain == value)
                .order_by(ResidualBaselineRecord.created_at.desc())
                .limit(1)
            )
            if entity_id is not None:
                statement = statement.where(ResidualBaselineRecord.entity_id == entity_id)
            if account_id is not None:
                statement = statement.where(ResidualBaselineRecord.account_id == account_id)
            if currency is not None:
                statement = statement.where(ResidualBaselineRecord.currency == currency)
            record = session.scalars(statement).first()
            return _record_to_baseline(record) if record else None


class ResidualBaselineManager:
    """Create and compare normal residual baselines."""

    def __init__(self, baseline_store: ResidualBaselineStore) -> None:
        self._store = baseline_store
        self._analyzer = ResidualDistributionAnalyzer()
        self._engine = ResidualIntelligenceEngine()

    def create_baseline(
        self,
        observations: Sequence[ResidualObservation],
        *,
        domain: ControlDomain,
        entity_id: str | None,
        account_id: str | None,
        currency: str,
        window_start: datetime,
        window_end: datetime,
    ) -> ResidualBaseline:
        ensure_single_currency(observations, currency)
        statistics = self._analyzer.analyze(observations)
        baseline = ResidualBaseline(
            baseline_id=f"baseline_{uuid4().hex}",
            domain=domain,
            entity_id=entity_id,
            account_id=account_id,
            currency=currency,
            window_start=window_start,
            window_end=window_end,
            sample_count=statistics.count,
            statistics=statistics,
            created_at=datetime.now(timezone.utc),
            sample_residuals=[observation.residual_amount for observation in observations],
        )
        return self._store.create_baseline(baseline)

    def get_baseline(self, baseline_id: str) -> ResidualBaseline | None:
        return self._store.get_baseline(baseline_id)

    def get_latest_baseline(
        self,
        domain: ControlDomain | str,
        *,
        entity_id: str | None = None,
        account_id: str | None = None,
        currency: str | None = None,
    ) -> ResidualBaseline | None:
        return self._store.get_latest_by_domain(
            domain,
            entity_id=entity_id,
            account_id=account_id,
            currency=currency,
        )

    def compare_to_baseline(
        self,
        baseline: ResidualBaseline,
        current: Sequence[ResidualObservation],
    ) -> ResidualAnalysis:
        return self._engine.analyze(current, baseline=baseline)


def _record_to_baseline(record: ResidualBaselineRecord) -> ResidualBaseline:
    return ResidualBaseline(
        baseline_id=record.baseline_id,
        domain=record.domain,
        entity_id=record.entity_id,
        account_id=record.account_id,
        currency=record.currency,
        window_start=datetime.fromisoformat(record.window_start),
        window_end=datetime.fromisoformat(record.window_end),
        sample_count=record.sample_count,
        statistics=ResidualDistributionStatistics.model_validate(
            json.loads(record.statistics_json)
        ),
        created_at=datetime.fromisoformat(record.created_at),
        sample_residuals=[
            Decimal(value) for value in json.loads(record.sample_residuals_json)
        ],
    )