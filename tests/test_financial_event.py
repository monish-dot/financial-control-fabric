"""Tests for the canonical FinancialEvent model."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.models.financial_event import EventType, FinancialEvent


def valid_event_data() -> dict[str, object]:
    """Return a representative synthetic event payload."""

    timestamp = datetime(2026, 9, 2, 12, 30, tzinfo=timezone.utc)
    return {
        "event_id": "evt_001",
        "event_type": "PAYMENT",
        "source_system": "payments",
        "source_id": "payment_001",
        "entity_id": "entity_001",
        "account_id": "account_001",
        "merchant_id": "merchant_001",
        "partner_id": "partner_001",
        "amount": "1250.105",
        "currency": "USD",
        "event_timestamp": timestamp,
        "effective_timestamp": timestamp,
        "status": "posted",
        "metadata": {"synthetic": True},
    }


def test_financial_event_parses_canonical_fields() -> None:
    event = FinancialEvent.model_validate(valid_event_data())

    assert event.event_id == "evt_001"
    assert event.event_type is EventType.PAYMENT
    assert event.amount == Decimal("1250.105")
    assert isinstance(event.amount, Decimal)
    assert event.currency == "USD"
    assert event.parent_event_id is None
    assert event.metadata == {"synthetic": True}


@pytest.mark.parametrize("event_type", [event_type.value for event_type in EventType])
def test_financial_event_supports_each_event_type(event_type: str) -> None:
    payload = valid_event_data()
    payload["event_type"] = event_type

    event = FinancialEvent.model_validate(payload)

    assert event.event_type.value == event_type


def test_financial_event_defaults_metadata_to_a_new_empty_dict() -> None:
    first_payload = valid_event_data()
    second_payload = valid_event_data()
    first_payload.pop("metadata")
    second_payload.pop("metadata")

    first = FinancialEvent.model_validate(first_payload)
    second = FinancialEvent.model_validate(second_payload)

    assert first.metadata == {}
    assert first.metadata is not second.metadata


def test_financial_event_rejects_unknown_event_type() -> None:
    payload = valid_event_data()
    payload["event_type"] = "UNKNOWN"

    with pytest.raises(ValidationError):
        FinancialEvent.model_validate(payload)


def test_financial_event_rejects_extra_fields() -> None:
    payload = valid_event_data()
    payload["unexpected"] = "not part of the canonical model"

    with pytest.raises(ValidationError):
        FinancialEvent.model_validate(payload)


def test_financial_event_rejects_invalid_currency() -> None:
    payload = valid_event_data()
    payload["currency"] = "US1"

    with pytest.raises(ValidationError):
        FinancialEvent.model_validate(payload)


def test_financial_event_rejects_lowercase_currency() -> None:
    payload = valid_event_data()
    payload["currency"] = "usd"

    with pytest.raises(ValidationError):
        FinancialEvent.model_validate(payload)