"""Integration tests for the read-only control API."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.database import Database
from data.control_scenarios import build_control_scenarios


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    database = Database(tmp_path / "financial_control.db")
    with TestClient(create_app(database)) as test_client:
        yield test_client
    database.dispose()


def test_list_controls(client: TestClient) -> None:
    response = client.get("/controls")

    assert response.status_code == 200
    assert {item["domain"] for item in response.json()} == {
        "NODAL_ESCROW",
        "SETTLEMENT",
        "MERCHANT_PAYOUT",
        "REVENUE_RECOGNITION",
        "CROSS_ENTITY",
    }


def test_get_control_definition(client: TestClient) -> None:
    response = client.get("/controls/nodal_escrow")

    assert response.status_code == 200
    assert response.json()["control_id"] == "nodal_escrow_balance"


def test_evaluate_passing_control_read_only(client: TestClient) -> None:
    scenario = next(
        scenario
        for scenario in build_control_scenarios()
        if scenario.name == "nodal_passing"
    )
    request = {
        "events": [
            event.model_dump(mode="json") for event in scenario.events
        ],
        "context": scenario.context.model_dump(mode="json"),
    }

    response = client.post("/controls/evaluate/nodal_escrow", json=request)

    assert response.status_code == 200
    assert response.json()["status"] == "PASS"
    assert response.json()["residual_amount"] == "0.00"
    assert client.get("/events").json() == []


def test_evaluate_failing_control(client: TestClient) -> None:
    scenario = next(
        scenario
        for scenario in build_control_scenarios()
        if scenario.name == "cross_entity_mismatch"
    )
    request = {
        "events": [
            event.model_dump(mode="json") for event in scenario.events
        ],
        "context": scenario.context.model_dump(mode="json"),
    }

    response = client.post("/controls/evaluate/cross_entity", json=request)

    assert response.status_code == 200
    assert response.json()["status"] == "FAIL"
    assert response.json()["residual_amount"] == "-50.00"