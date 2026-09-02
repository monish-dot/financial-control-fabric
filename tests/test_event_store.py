"""Integration tests for the SQLite event store API."""

from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.database import Database


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    database = Database(tmp_path / "financial_control.db")
    with TestClient(create_app(database)) as test_client:
        yield test_client
    database.dispose()


def event_payload(
    event_id: str = "evt_001",
    *,
    event_type: str = "PAYMENT",
    entity_id: str = "entity_001",
    account_id: str = "account_001",
    merchant_id: str | None = "merchant_001",
    amount: str = "1250.105",
) -> dict[str, object]:
    timestamp = datetime(2026, 9, 2, 12, 30, tzinfo=timezone.utc).isoformat()
    return {
        "event_id": event_id,
        "event_type": event_type,
        "source_system": "synthetic_payments",
        "source_id": f"source_{event_id}",
        "entity_id": entity_id,
        "account_id": account_id,
        "merchant_id": merchant_id,
        "partner_id": "partner_001",
        "amount": amount,
        "currency": "INR",
        "event_timestamp": timestamp,
        "effective_timestamp": timestamp,
        "status": "posted",
        "metadata": {"synthetic": True},
    }


def create(client: TestClient, payload: dict[str, object]) -> dict[str, object]:
    response = client.post("/events", json=payload)
    assert response.status_code == 201
    return response.json()


def test_create_event(client: TestClient) -> None:
    body = create(client, event_payload())

    assert body["created"] is True
    assert body["message"] == "event created"
    assert body["event"]["event_id"] == "evt_001"


def test_retrieve_event(client: TestClient) -> None:
    create(client, event_payload())

    response = client.get("/events/evt_001")

    assert response.status_code == 200
    assert response.json()["event_id"] == "evt_001"
    assert response.json()["amount"] == str(Decimal("1250.105"))


def test_list_events(client: TestClient) -> None:
    create(client, event_payload("evt_001"))
    create(client, event_payload("evt_002"))

    response = client.get("/events")

    assert response.status_code == 200
    assert [event["event_id"] for event in response.json()] == ["evt_001", "evt_002"]


def test_event_type_filtering(client: TestClient) -> None:
    create(client, event_payload("payment", event_type="PAYMENT"))
    create(client, event_payload("refund", event_type="REFUND"))

    response = client.get("/events", params={"event_type": "REFUND"})

    assert [event["event_id"] for event in response.json()] == ["refund"]


def test_entity_filtering(client: TestClient) -> None:
    create(client, event_payload("entity-a", entity_id="entity_a"))
    create(client, event_payload("entity-b", entity_id="entity_b"))

    response = client.get("/events", params={"entity_id": "entity_b"})

    assert [event["event_id"] for event in response.json()] == ["entity-b"]


def test_account_filtering(client: TestClient) -> None:
    create(client, event_payload("account-a", account_id="account_a"))
    create(client, event_payload("account-b", account_id="account_b"))

    response = client.get("/events", params={"account_id": "account_b"})

    assert [event["event_id"] for event in response.json()] == ["account-b"]


def test_merchant_filtering(client: TestClient) -> None:
    create(client, event_payload("merchant-a", merchant_id="merchant_a"))
    create(client, event_payload("merchant-b", merchant_id="merchant_b"))

    response = client.get("/events", params={"merchant_id": "merchant_b"})

    assert [event["event_id"] for event in response.json()] == ["merchant-b"]


def test_pagination(client: TestClient) -> None:
    for index in range(4):
        create(client, event_payload(f"evt_{index:03d}"))

    response = client.get("/events", params={"limit": 2, "offset": 1})

    assert [event["event_id"] for event in response.json()] == ["evt_001", "evt_002"]


def test_duplicate_event_id_is_idempotent(client: TestClient) -> None:
    first = create(client, event_payload(amount="10.00"))
    duplicate = client.post("/events", json=event_payload(amount="999.00"))

    assert duplicate.status_code == 200
    assert duplicate.json()["created"] is False
    assert duplicate.json()["message"] == "event already exists"
    assert duplicate.json()["event"] == first["event"]
    assert len(client.get("/events").json()) == 1


def test_invalid_decimal_amount(client: TestClient) -> None:
    response = client.post("/events", json=event_payload(amount="not-a-decimal"))

    assert response.status_code == 422
    assert "amount" in response.text


def test_invalid_currency(client: TestClient) -> None:
    payload = event_payload()
    payload["currency"] = "inr"

    response = client.post("/events", json=payload)

    assert response.status_code == 422
    assert "currency" in response.text


def test_event_persists_after_database_restart(tmp_path) -> None:
    database_path = tmp_path / "financial_control.db"
    first_database = Database(database_path)
    with TestClient(create_app(first_database)) as first_client:
        create(first_client, event_payload("persistent-event"))
    first_database.dispose()

    second_database = Database(database_path)
    with TestClient(create_app(second_database)) as second_client:
        response = second_client.get("/events/persistent-event")
    second_database.dispose()

    assert response.status_code == 200
    assert response.json()["event_id"] == "persistent-event"