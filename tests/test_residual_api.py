"""Integration tests for the read-only residual intelligence API."""

from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from backend.anomaly.residual_store import ResidualStore
from backend.api.main import create_app
from backend.database import Database
from data.residual_scenarios import build_residual_populations


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    database = Database(tmp_path / "financial_control.db")
    database.initialize()
    store = ResidualStore(database.session_factory)
    for observation in build_residual_populations()["stable"]:
        store.record_residual(observation)
    with TestClient(create_app(database)) as test_client:
        yield test_client
    database.dispose()


def test_list_and_get_residuals(client: TestClient) -> None:
    listed = client.get("/residuals", params={"domain": "NODAL_ESCROW"})
    retrieved = client.get("/residuals/stable_001")

    assert listed.status_code == 200
    assert len(listed.json()) == 8
    assert retrieved.status_code == 200
    assert retrieved.json()["residual_id"] == "stable_001"


def test_distribution_endpoint(client: TestClient) -> None:
    response = client.get("/residuals/distribution/NODAL_ESCROW")

    assert response.status_code == 200
    assert response.json()["statistics"]["count"] == 8
    assert response.json()["statistics"]["zero_residual_ratio"] == "0.75"


def test_analysis_endpoint_with_stable_and_anomalous_populations(
    client: TestClient,
) -> None:
    populations = build_residual_populations()
    stable_request = {
        "residuals": [
            observation.model_dump(mode="json")
            for observation in populations["stable"]
        ],
        "baseline_residuals": [
            observation.model_dump(mode="json")
            for observation in populations["stable"]
        ],
    }
    anomalous_request = {
        "residuals": [
            observation.model_dump(mode="json")
            for observation in populations["persistent_positive_bias"]
        ],
        "baseline_residuals": [
            observation.model_dump(mode="json")
            for observation in populations["stable"]
        ],
    }

    stable = client.post(
        "/residuals/analyze/NODAL_ESCROW",
        json=stable_request,
    )
    anomalous = client.post(
        "/residuals/analyze/NODAL_ESCROW",
        json=anomalous_request,
    )

    assert stable.status_code == 200
    assert stable.json()["anomaly_score"]["severity"] == "NORMAL"
    assert anomalous.status_code == 200
    assert Decimal(anomalous.json()["anomaly_score"]["score"]) > Decimal("0")
    assert anomalous.json()["anomaly_score"]["signals"]
    assert len(client.get("/residuals").json()) == 8


def test_empty_distribution_and_unknown_domain(client: TestClient) -> None:
    empty = client.get(
        "/residuals/distribution/SETTLEMENT",
        params={"currency": "INR"},
    )
    unknown = client.get("/residuals/distribution/unknown")

    assert empty.status_code == 200
    assert empty.json()["statistics"]["count"] == 0
    assert unknown.status_code == 404


def test_baseline_endpoint(client: TestClient) -> None:
    response = client.get("/residuals/baseline/NODAL_ESCROW")

    assert response.status_code == 404