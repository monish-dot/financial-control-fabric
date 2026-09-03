"""API lifecycle and safety tests for the Finance Controller."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from backend.anomaly.engine import ResidualIntelligenceEngine
from backend.api.main import create_app
from backend.controls.models import ControlDomain, ControlResult, ControlStatus
from backend.database.connection import Database
from backend.models.financial_event import EventType, FinancialEvent


START = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def client(tmp_path):
    database = Database(tmp_path / "financial_control.db")
    database.initialize()
    with TestClient(create_app(database)) as test_client:
        yield test_client
    database.dispose()


def test_agent_api_lifecycle_and_read_only_boundary(client: TestClient) -> None:
    payment = _event("payment-api", EventType.PAYMENT, "10000")
    created = client.post("/events", json=payment.model_dump(mode="json"))
    assert created.status_code == 201
    before = client.get("/events").json()

    request = _request("api-investigation", "10000", "9000")
    investigation = client.post(
        "/agent/investigate",
        json=request.model_dump(mode="json"),
    )

    assert investigation.status_code == 200
    report = investigation.json()
    assert report["status"] == "COMPLETED"
    assert report["root_causes"][0]["category"] == "MISSING_EVENT"
    assert report["hypotheses"]
    assert report["evidence"]
    assert report["calculations"]
    assert report["requires_human_approval"] is True
    assert report["metadata"]["financial_mutation_executed"] is False

    retrieved = client.get("/agent/investigations/api-investigation")
    evidence = client.get("/agent/investigations/api-investigation/evidence")
    hypotheses = client.get("/agent/investigations/api-investigation/hypotheses")
    audit = client.get("/agent/investigations/api-investigation/audit")
    assert retrieved.status_code == 200
    assert retrieved.json() == report
    assert evidence.status_code == 200
    assert hypotheses.status_code == 200
    assert audit.status_code == 200
    assert any(event["tool_name"] == "search_events" for event in audit.json())

    action = client.post(
        "/agent/investigations/api-investigation/recommendation"
    )
    assert action.status_code == 200
    assert action.json()["approval_status"] == "PENDING"
    assert action.json()["requires_approval"] is True

    approval = client.post(
        "/agent/investigations/api-investigation/approve",
        json={"approved": True, "approved_by": "human-controller"},
    )
    assert approval.status_code == 200
    assert approval.json()["approval_status"] == "APPROVED"

    new_result = _control_result("api-investigation", "100", "100")
    revalidation = client.post(
        "/agent/investigations/api-investigation/revalidate",
        json={"new_control_result": new_result.model_dump(mode="json")},
    )
    assert revalidation.status_code == 200
    assert revalidation.json()["resolved"] is True
    assert client.get("/events").json() == before


def test_agent_api_enforces_approval_and_unknown_investigation(client: TestClient) -> None:
    request = _request("api-approval", "100", "90")
    assert client.post(
        "/agent/investigate",
        json=request.model_dump(mode="json"),
    ).status_code == 200
    blocked = client.post(
        "/agent/investigations/api-approval/revalidate",
        json={"new_control_result": request.control_result.model_dump(mode="json")},
    )
    unknown = client.get("/agent/investigations/not-found")

    assert blocked.status_code == 400
    assert "approved action" in blocked.json()["detail"]
    assert unknown.status_code == 404


def test_insufficient_evidence_api_report(client: TestClient) -> None:
    request = _request("api-unknown", "1000", "900")
    response = client.post(
        "/agent/investigate",
        json=request.model_dump(mode="json"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "INCONCLUSIVE"
    assert body["root_causes"][0]["category"] == "UNKNOWN"
    assert body["root_causes"][0]["retrieval_status"] == "INSUFFICIENT_EVIDENCE"
    assert body["root_causes"][0]["reasoning_status"] == "INCONCLUSIVE"


def _request(investigation_id: str, expected: str, actual: str):
    from backend.agent.models import InvestigationRequest

    residual = Decimal(actual) - Decimal(expected)
    analysis = ResidualIntelligenceEngine().analyze(
        [_residual(f"{investigation_id}-current", residual)],
        baseline_residuals=[_residual(f"{investigation_id}-baseline", Decimal("0"))],
    )
    return InvestigationRequest(
        investigation_id=investigation_id,
        control_id=f"{investigation_id}-control",
        domain=ControlDomain.MERCHANT_PAYOUT,
        entity_id="entity-a",
        account_id="account-a",
        merchant_id="merchant-a",
        partner_id="partner-a",
        period_start=START,
        period_end=START + timedelta(hours=1),
        control_result=_control_result(investigation_id, expected, actual),
        anomaly_score=analysis.anomaly_score,
        residual_summary=analysis,
    )


def _control_result(control_id: str, expected: str, actual: str) -> ControlResult:
    expected_amount = Decimal(expected)
    actual_amount = Decimal(actual)
    return ControlResult(
        control_id=control_id,
        domain=ControlDomain.MERCHANT_PAYOUT,
        entity_id="entity-a",
        period_start=START,
        period_end=START + timedelta(hours=1),
        expected_amount=expected_amount,
        actual_amount=actual_amount,
        residual_amount=actual_amount - expected_amount,
        currency="INR",
        status=ControlStatus.PASS if expected_amount == actual_amount else ControlStatus.FAIL,
        tolerance=Decimal("0"),
        explanation="synthetic",
    )


def _residual(residual_id: str, amount: Decimal):
    from backend.anomaly.residual_models import ResidualObservation

    return ResidualObservation(
        residual_id=residual_id,
        control_id="synthetic",
        domain=ControlDomain.MERCHANT_PAYOUT,
        timestamp=START,
        expected_amount=Decimal("0"),
        actual_amount=amount,
        residual_amount=amount,
        currency="INR",
        status=ControlStatus.PASS if amount == 0 else ControlStatus.FAIL,
    )


def _event(event_id: str, event_type: EventType, amount: str) -> FinancialEvent:
    return FinancialEvent(
        event_id=event_id,
        event_type=event_type,
        source_system="synthetic",
        source_id=event_id,
        entity_id="entity-a",
        account_id="account-a",
        merchant_id="merchant-a",
        partner_id="partner-a",
        amount=Decimal(amount),
        currency="INR",
        event_timestamp=START,
        effective_timestamp=START,
        status="POSTED",
    )