"""API tests for read-only settlement reconciliation."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.database import Database


@pytest.fixture
def client(tmp_path):
    database = Database(tmp_path / "financial_control.db")
    database.initialize()
    with TestClient(create_app(database)) as test_client:
        yield test_client
    database.dispose()


def test_settlement_reconciliation_post_and_get(client: TestClient) -> None:
    response = client.post(
        "/reconciliation/settlement",
        json={
            "reconciliation_id": "api-reconciliation",
            "internal_items": [
                _item("I1", "100", "INTERNAL"),
                _item("I2", "200", "INTERNAL"),
                _item("I3", "300", "INTERNAL"),
            ],
            "external_items": [
                _item("E1", "250", "EXTERNAL"),
                _item("E2", "350", "EXTERNAL"),
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reconciliation_id"] == "api-reconciliation"
    assert body["matched_amount"] == "600"
    assert body["status"] == "FULLY_RECONCILED"
    assert body["allocation_count"] == 4
    assert "capacity constraints satisfied" in body["explanation"]

    retrieved = client.get("/reconciliation/api-reconciliation")
    assert retrieved.status_code == 200
    assert retrieved.json() == body


def test_settlement_reconciliation_rejects_mixed_currency(client: TestClient) -> None:
    response = client.post(
        "/reconciliation/settlement",
        json={
            "internal_items": [_item("I1", "1000", "INTERNAL", currency="INR")],
            "external_items": [_item("E1", "1000", "EXTERNAL", currency="USD")],
        },
    )

    assert response.status_code == 400
    assert "mixed currencies" in response.json()["detail"]


def test_get_unknown_reconciliation_returns_404(client: TestClient) -> None:
    response = client.get("/reconciliation/not-found")

    assert response.status_code == 404


def _item(item_id: str, amount: str, side: str, *, currency: str = "INR") -> dict:
    return {
        "item_id": item_id,
        "side": side,
        "item_type": (
            "SETTLEMENT_OBLIGATION"
            if side == "INTERNAL"
            else "BANK_SETTLEMENT"
        ),
        "entity_id": "entity-a",
        "account_id": "account-a",
        "merchant_id": "merchant-a",
        "partner_id": "partner-a",
        "amount": amount,
        "currency": currency,
        "timestamp": datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc).isoformat(),
        "reference_id": None,
        "status": "OPEN",
        "metadata": {},
    }