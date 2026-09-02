"""Persistence service for residual observations."""

import json
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.anomaly.residual_models import ResidualObservation, ResidualVector
from backend.database.models import ResidualObservationRecord
from backend.controls.models import ControlDomain


class ResidualStore:
    """Store and query residual observations without mutating financial events."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def record_residual(self, residual: ResidualObservation) -> ResidualObservation:
        """Persist a residual, returning the existing observation for duplicate IDs."""

        with self._session_factory() as session:
            existing = session.get(ResidualObservationRecord, residual.residual_id)
            if existing is not None:
                return _record_to_observation(existing)

            session.add(_observation_to_record(residual))
            session.commit()
            return residual

    def get_residual(self, residual_id: str) -> ResidualObservation | None:
        with self._session_factory() as session:
            record = session.get(ResidualObservationRecord, residual_id)
            return _record_to_observation(record) if record is not None else None

    def list_residuals(
        self,
        *,
        domain: ControlDomain | str | None = None,
        entity_id: str | None = None,
        account_id: str | None = None,
        merchant_id: str | None = None,
        partner_id: str | None = None,
        currency: str | None = None,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ResidualObservation]:
        """List observations using optional analytical-scope filters."""

        with self._session_factory() as session:
            statement = select(ResidualObservationRecord)
            if domain is not None:
                value = domain.value if isinstance(domain, ControlDomain) else domain
                statement = statement.where(ResidualObservationRecord.domain == value)
            if entity_id is not None:
                statement = statement.where(ResidualObservationRecord.entity_id == entity_id)
            if account_id is not None:
                statement = statement.where(ResidualObservationRecord.account_id == account_id)
            if merchant_id is not None:
                statement = statement.where(ResidualObservationRecord.merchant_id == merchant_id)
            if partner_id is not None:
                statement = statement.where(ResidualObservationRecord.partner_id == partner_id)
            if currency is not None:
                statement = statement.where(ResidualObservationRecord.currency == currency)
            if window_start is not None:
                statement = statement.where(
                    ResidualObservationRecord.timestamp >= window_start.isoformat()
                )
            if window_end is not None:
                statement = statement.where(
                    ResidualObservationRecord.timestamp <= window_end.isoformat()
                )

            statement = statement.order_by(
                ResidualObservationRecord.timestamp,
                ResidualObservationRecord.residual_id,
            ).offset(offset)
            if limit is not None:
                statement = statement.limit(limit)
            records = session.scalars(statement).all()
            return [_record_to_observation(record) for record in records]

    def list_residuals_by_domain(
        self, domain: ControlDomain | str, **kwargs: object
    ) -> list[ResidualObservation]:
        return self.list_residuals(domain=domain, **kwargs)

    def list_residuals_by_entity(
        self, entity_id: str, **kwargs: object
    ) -> list[ResidualObservation]:
        return self.list_residuals(entity_id=entity_id, **kwargs)

    def list_residuals_by_account(
        self, account_id: str, **kwargs: object
    ) -> list[ResidualObservation]:
        return self.list_residuals(account_id=account_id, **kwargs)

    def list_residuals_by_merchant(
        self, merchant_id: str, **kwargs: object
    ) -> list[ResidualObservation]:
        return self.list_residuals(merchant_id=merchant_id, **kwargs)

    def list_residuals_by_period(
        self, window_start: datetime, window_end: datetime, **kwargs: object
    ) -> list[ResidualObservation]:
        return self.list_residuals(
            window_start=window_start,
            window_end=window_end,
            **kwargs,
        )


def _observation_to_record(observation: ResidualObservation) -> ResidualObservationRecord:
    return ResidualObservationRecord(
        residual_id=observation.residual_id,
        control_id=observation.control_id,
        domain=observation.domain.value,
        entity_id=observation.entity_id,
        account_id=observation.account_id,
        merchant_id=observation.merchant_id,
        partner_id=observation.partner_id,
        timestamp=observation.timestamp.isoformat(),
        expected_amount=format(observation.expected_amount, "f"),
        actual_amount=format(observation.actual_amount, "f"),
        residual_amount=format(observation.residual_amount, "f"),
        currency=observation.currency,
        status=observation.status.value,
        metadata_json=json.dumps(observation.metadata, sort_keys=True, default=str),
        vector_json=(
            json.dumps(observation.vector.model_dump(mode="json"), sort_keys=True)
            if observation.vector is not None
            else None
        ),
    )


def _record_to_observation(
    record: ResidualObservationRecord,
) -> ResidualObservation:
    vector = (
        ResidualVector.model_validate(json.loads(record.vector_json))
        if record.vector_json is not None
        else None
    )
    return ResidualObservation(
        residual_id=record.residual_id,
        control_id=record.control_id,
        domain=record.domain,
        entity_id=record.entity_id,
        account_id=record.account_id,
        merchant_id=record.merchant_id,
        partner_id=record.partner_id,
        timestamp=datetime.fromisoformat(record.timestamp),
        expected_amount=Decimal(record.expected_amount),
        actual_amount=Decimal(record.actual_amount),
        residual_amount=Decimal(record.residual_amount),
        currency=record.currency,
        status=record.status,
        metadata=json.loads(record.metadata_json),
        vector=vector,
    )