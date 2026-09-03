"""Repository for deterministic persistence of canonical financial events."""

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database.models import FinancialEventRecord
from backend.models.financial_event import EventType, FinancialEvent


@dataclass(frozen=True)
class CreateEventResult:
    """Result of an idempotent event creation request."""

    event: FinancialEvent
    created: bool


class FinancialEventRepository:
    """Persist and query FinancialEvent instances without financial logic."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def create_event(self, event: FinancialEvent) -> CreateEventResult:
        """Create an event, returning the existing record for duplicate IDs."""

        with self._session_factory() as session:
            existing = session.get(FinancialEventRecord, event.event_id)
            if existing is not None:
                return CreateEventResult(event=_record_to_event(existing), created=False)

            session.add(_event_to_record(event))
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                existing = session.get(FinancialEventRecord, event.event_id)
                if existing is not None:
                    return CreateEventResult(event=_record_to_event(existing), created=False)
                raise

            return CreateEventResult(
                event=_record_to_event(session.get(FinancialEventRecord, event.event_id)),
                created=True,
            )

    def get_event(self, event_id: str) -> FinancialEvent | None:
        """Retrieve one event by its unique identifier."""

        with self._session_factory() as session:
            record = session.get(FinancialEventRecord, event_id)
            return _record_to_event(record) if record is not None else None

    def list_events(
        self,
        *,
        event_type: EventType | str | None = None,
        event_types: set[EventType | str] | None = None,
        entity_id: str | None = None,
        account_id: str | None = None,
        merchant_id: str | None = None,
        partner_id: str | None = None,
        currency: str | None = None,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        reference_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[FinancialEvent]:
        """List events using optional filters and deterministic pagination."""

        with self._session_factory() as session:
            statement = select(FinancialEventRecord)
            if event_type is not None:
                statement = statement.where(
                    FinancialEventRecord.event_type == _event_type_value(event_type)
                )
            if event_types is not None:
                statement = statement.where(
                    FinancialEventRecord.event_type.in_(
                        [_event_type_value(value) for value in event_types]
                    )
                )
            if entity_id is not None:
                statement = statement.where(FinancialEventRecord.entity_id == entity_id)
            if account_id is not None:
                statement = statement.where(FinancialEventRecord.account_id == account_id)
            if merchant_id is not None:
                statement = statement.where(FinancialEventRecord.merchant_id == merchant_id)
            if partner_id is not None:
                statement = statement.where(FinancialEventRecord.partner_id == partner_id)
            if currency is not None:
                statement = statement.where(FinancialEventRecord.currency == currency)
            if period_start is not None:
                statement = statement.where(
                    FinancialEventRecord.event_timestamp >= period_start.isoformat()
                )
            if period_end is not None:
                statement = statement.where(
                    FinancialEventRecord.event_timestamp <= period_end.isoformat()
                )
            if reference_id is not None:
                statement = statement.where(
                    FinancialEventRecord.source_id == reference_id
                )

            statement = statement.order_by(
                FinancialEventRecord.event_timestamp,
                FinancialEventRecord.event_id,
            ).offset(offset)
            if limit is not None:
                statement = statement.limit(limit)

            records = session.scalars(statement).all()
            return [_record_to_event(record) for record in records]

    def list_events_by_type(
        self, event_type: EventType | str, *, limit: int | None = None, offset: int = 0
    ) -> list[FinancialEvent]:
        """List events matching one event type."""

        return self.list_events(event_type=event_type, limit=limit, offset=offset)

    def list_events_by_entity(
        self, entity_id: str, *, limit: int | None = None, offset: int = 0
    ) -> list[FinancialEvent]:
        """List events belonging to one entity."""

        return self.list_events(entity_id=entity_id, limit=limit, offset=offset)

    def list_events_by_account(
        self, account_id: str, *, limit: int | None = None, offset: int = 0
    ) -> list[FinancialEvent]:
        """List events belonging to one account."""

        return self.list_events(account_id=account_id, limit=limit, offset=offset)

    def list_events_by_merchant(
        self, merchant_id: str, *, limit: int | None = None, offset: int = 0
    ) -> list[FinancialEvent]:
        """List events belonging to one merchant."""

        return self.list_events(merchant_id=merchant_id, limit=limit, offset=offset)


def _event_type_value(event_type: EventType | str) -> str:
    return event_type.value if isinstance(event_type, EventType) else event_type


def _event_to_record(event: FinancialEvent) -> FinancialEventRecord:
    return FinancialEventRecord(
        event_id=event.event_id,
        event_type=event.event_type.value,
        source_system=event.source_system,
        source_id=event.source_id,
        entity_id=event.entity_id,
        account_id=event.account_id,
        merchant_id=event.merchant_id,
        partner_id=event.partner_id,
        amount=format(event.amount, "f"),
        currency=event.currency,
        event_timestamp=event.event_timestamp.isoformat(),
        effective_timestamp=event.effective_timestamp.isoformat(),
        status=event.status,
        parent_event_id=event.parent_event_id,
        metadata_json=json.dumps(event.metadata, sort_keys=True, default=str),
    )


def _record_to_event(record: FinancialEventRecord | None) -> FinancialEvent:
    if record is None:
        raise ValueError("cannot convert a missing financial event record")

    return FinancialEvent(
        event_id=record.event_id,
        event_type=record.event_type,
        source_system=record.source_system,
        source_id=record.source_id,
        entity_id=record.entity_id,
        account_id=record.account_id,
        merchant_id=record.merchant_id,
        partner_id=record.partner_id,
        amount=Decimal(record.amount),
        currency=record.currency,
        event_timestamp=datetime.fromisoformat(record.event_timestamp),
        effective_timestamp=datetime.fromisoformat(record.effective_timestamp),
        status=record.status,
        parent_event_id=record.parent_event_id,
        metadata=json.loads(record.metadata_json),
    )