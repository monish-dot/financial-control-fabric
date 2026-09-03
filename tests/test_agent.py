"""Tests for the guarded AI Finance Controller."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.agent.calculator import DeterministicCalculator
from backend.agent.investigator import FinanceController
from backend.agent.llm import MockLLMProvider
from backend.agent.models import (
    AgentState,
    ApprovalStatus,
    AuditActor,
    ControllerAction,
    EvidenceItem,
    InvestigationHypothesis,
    InvestigationReport,
    InvestigationRequest,
    InvestigationStatus,
    RevalidationRequest,
    ReasoningStatus,
    RetrievalStatus,
    RootCauseCategory,
    ToolQuery,
)
from backend.agent.state_machine import InvestigationStateMachine
from backend.agent.tools import ReadOnlyFinancialTools
from backend.anomaly.engine import ResidualIntelligenceEngine
from backend.anomaly.residual_models import ResidualObservation
from backend.controls.models import ControlDomain, ControlResult, ControlStatus
from backend.database.connection import Database
from backend.models.financial_event import EventType, FinancialEvent
from backend.repositories.financial_event import FinancialEventRepository


START = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def controller_context(tmp_path):
    database = Database(tmp_path / "financial_control.db")
    database.initialize()
    repository = FinancialEventRepository(database.session_factory)
    controller = FinanceController(repository)
    yield controller, repository, database
    database.dispose()


def test_investigation_creation_and_report_shape(controller_context) -> None:
    controller, _, database = controller_context
    request = _request("creation", ControlDomain.MERCHANT_PAYOUT)

    report = controller.investigate(request)

    assert report.status is InvestigationStatus.INCONCLUSIVE
    assert report.investigation_id == "creation"
    assert report.hypotheses
    assert report.anomaly_score
    assert report.requires_human_approval is True
    assert report.audit_ids
    assert database.engine.url.database


def test_tool_schema_validation_and_bounded_read_only_behavior(controller_context) -> None:
    _, repository, database = controller_context
    event = _event("payment-1", EventType.PAYMENT, "100")
    repository.create_event(event)
    tools = ReadOnlyFinancialTools(repository)

    result = tools.search_payments(ToolQuery(limit=1))
    retrieved = tools.get_event("payment-1")

    assert result.count == 1
    assert result.items[0].event_id == "payment-1"
    assert retrieved.items[0] == event
    assert not hasattr(tools, "create_event")
    with pytest.raises(ValidationError):
        ToolQuery(limit=101, unexpected="blocked")
    assert repository.get_event("payment-1") == event
    database.dispose()


def test_calculator_is_deterministic_and_decimal_only() -> None:
    calculator = DeterministicCalculator()

    first = calculator.calculate_merchant_entitlement(
        currency="INR",
        gross_amount=Decimal("10000"),
        fees=Decimal("100"),
        taxes=Decimal("50"),
        refunds=Decimal("25"),
    )
    second = calculator.calculate_merchant_entitlement(
        currency="INR",
        gross_amount=Decimal("10000"),
        fees=Decimal("100"),
        taxes=Decimal("50"),
        refunds=Decimal("25"),
    )

    assert first.result == Decimal("9825")
    assert first.formula == "gross - fees - taxes - refunds + adjustments"
    assert first.calculation_trace[-1] == "result: 9825"
    assert first.model_dump() == second.model_dump()


def test_evidence_and_hypothesis_models_require_traceable_fields() -> None:
    evidence = EvidenceItem(
        evidence_id="e1",
        source_type="PAYMENT",
        source_id="payment-1",
        field="amount",
        value=Decimal("100"),
        timestamp=START,
        relevance=Decimal("1"),
    )
    hypothesis = InvestigationHypothesis(
        hypothesis_id="h1",
        description="missing payout",
        confidence=Decimal("0.8"),
        status="SUPPORTED",
        retrieval_status="SUCCESS",
        reasoning_status="CONSISTENT",
        supporting_evidence=[evidence.evidence_id],
        explanation="Supported by retrieved evidence.",
    )

    assert hypothesis.supporting_evidence == ["e1"]
    assert evidence.source_id == "payment-1"


def test_hypothesis_rejection_and_support(controller_context) -> None:
    controller, repository, _ = controller_context
    repository.create_event(_event("payout-a", EventType.PAYOUT, "100"))
    report = controller.investigate(
        _request(
            "rejection",
            ControlDomain.MERCHANT_PAYOUT,
            expected="100",
            actual="100",
        )
    )

    payout_hypothesis = next(
        hypothesis
        for hypothesis in report.hypotheses
        if hypothesis.description == "missing payout"
    )
    assert payout_hypothesis.status.value == "REJECTED"
    assert payout_hypothesis.reasoning_status is ReasoningStatus.CONTRADICTED


def test_missing_payout_scenario(controller_context) -> None:
    controller, repository, _ = controller_context
    repository.create_event(_event("payment-10000", EventType.PAYMENT, "10000"))

    report = controller.investigate(
        _request("missing-payout", ControlDomain.MERCHANT_PAYOUT, "10000", "9000")
    )

    finding = report.root_causes[0]
    assert finding.category is RootCauseCategory.MISSING_EVENT
    assert finding.supporting_evidence
    assert finding.retrieval_status is RetrievalStatus.SUCCESS
    assert "MISSING_EVENT" in report.summary
    assert report.calculations[0].result == Decimal("10000")


def test_duplicate_payout_scenario(controller_context) -> None:
    controller, repository, _ = controller_context
    repository.create_event(
        _event("payout-1", EventType.PAYOUT, "6000", source_id="same-payout")
    )
    repository.create_event(
        _event("payout-2", EventType.PAYOUT, "5000", source_id="same-payout")
    )

    report = controller.investigate(
        _request("duplicate-payout", ControlDomain.MERCHANT_PAYOUT, "10000", "11000")
    )

    assert report.root_causes[0].category is RootCauseCategory.DUPLICATE_EVENT
    assert len(report.root_causes[0].supporting_evidence) == 2


def test_timing_difference_scenario(controller_context) -> None:
    controller, repository, _ = controller_context
    repository.create_event(
        _event("settlement-1", EventType.SETTLEMENT, "1000")
    )
    repository.create_event(
        _event(
            "bank-1",
            EventType.BANK_CREDIT,
            "1000",
            timestamp=START + timedelta(minutes=23),
        )
    )

    report = controller.investigate(
        _request("timing", ControlDomain.SETTLEMENT, "1000", "1000")
    )

    assert report.root_causes[0].category is RootCauseCategory.TIMING_DIFFERENCE
    assert "23" in report.root_causes[0].description


def test_fee_difference_scenario(controller_context) -> None:
    controller, repository, _ = controller_context
    repository.create_event(_event("fee-1", EventType.FEE, "120"))

    report = controller.investigate(
        _request(
            "fee",
            ControlDomain.MERCHANT_PAYOUT,
            "100",
            "120",
            metadata={"expected_fee": "100"},
        )
    )

    assert report.root_causes[0].category is RootCauseCategory.FEE_DIFFERENCE
    assert report.recommended_action.value == "REVIEW_FEE"


def test_insufficient_evidence_scenario(controller_context) -> None:
    controller, _, _ = controller_context

    report = controller.investigate(
        _request("unknown", ControlDomain.SETTLEMENT, "1000", "900")
    )

    finding = report.root_causes[0]
    assert finding.category is RootCauseCategory.UNKNOWN
    assert finding.retrieval_status is RetrievalStatus.INSUFFICIENT_EVIDENCE
    assert finding.reasoning_status is ReasoningStatus.INCONCLUSIVE
    assert report.status is InvestigationStatus.INCONCLUSIVE


def test_state_machine_rejects_invalid_transition() -> None:
    machine = InvestigationStateMachine()

    with pytest.raises(ValueError, match="invalid investigation transition"):
        machine.transition(AgentState.RESOLVED)
    machine.transition(AgentState.INVESTIGATING)
    with pytest.raises(ValueError):
        machine.transition(AgentState.RESOLVED)


def test_recommendation_approval_and_revalidation(controller_context) -> None:
    controller, repository, _ = controller_context
    repository.create_event(_event("payment-1", EventType.PAYMENT, "10000"))
    request = _request("approval", ControlDomain.MERCHANT_PAYOUT, "10000", "9000")
    controller.investigate(request)

    action = controller.request_recommendation("approval")
    assert action.approval_status is ApprovalStatus.PENDING
    assert action.requires_approval is True
    with pytest.raises(ValueError, match="current investigation state"):
        controller.revalidate("approval", request.control_result)

    approved = controller.approve(
        "approval",
        approved=True,
        approved_by="controller-user",
    )
    assert approved.approval_status is ApprovalStatus.APPROVED
    assert approved.approved_by == "controller-user"
    new_result = _control_result("approval", "100", "100", ControlDomain.MERCHANT_PAYOUT)
    validation = controller.revalidate("approval", new_result)
    assert validation.resolved is True
    assert validation.previous_residual == Decimal("-1000")
    assert validation.new_status is ControlStatus.PASS


def test_agent_cannot_create_approved_action() -> None:
    with pytest.raises(ValidationError, match="agent-proposed"):
        ControllerAction(
            action_id="a1",
            investigation_id="i1",
            action_type="REVIEW_FEE",
            description="review",
            proposed_by=AuditActor.AGENT,
            requires_approval=True,
            approval_status=ApprovalStatus.APPROVED,
        )


def test_mock_llm_provider_and_deterministic_repeated_investigation(controller_context) -> None:
    controller, _, _ = controller_context
    request = _request("repeat", ControlDomain.SETTLEMENT, "100", "90")

    first = controller.investigate(request)
    second = controller.investigate(request)
    provider = MockLLMProvider()

    assert first.model_dump() == second.model_dump()
    assert provider.generate_hypotheses(request) == []
    assert provider.summarize_evidence([]) == "0 bounded evidence item(s) collected."


@pytest.mark.parametrize("domain", list(ControlDomain))
def test_multi_domain_investigation(controller_context, domain: ControlDomain) -> None:
    controller, _, _ = controller_context

    report = controller.investigate(
        _request(f"domain-{domain.value}", domain, "100", "90")
    )

    assert report.domain is domain
    assert report.requires_human_approval is True


def _request(
    investigation_id: str,
    domain: ControlDomain,
    expected: str = "100",
    actual: str = "90",
    *,
    metadata: dict | None = None,
) -> InvestigationRequest:
    analysis = ResidualIntelligenceEngine().analyze(
        [
            _residual(
                f"{investigation_id}-current",
                _decimal(actual) - _decimal(expected),
            ),
        ],
        baseline_residuals=[_residual(f"{investigation_id}-baseline", Decimal("0"))],
    )
    return InvestigationRequest(
        investigation_id=investigation_id,
        control_id=f"{domain.value.lower()}-control",
        domain=domain,
        entity_id="entity-a",
        account_id="account-a",
        merchant_id="merchant-a",
        partner_id="partner-a",
        period_start=START,
        period_end=START + timedelta(hours=1),
        control_result=_control_result(investigation_id, expected, actual, domain, metadata),
        anomaly_score=analysis.anomaly_score,
        residual_summary=analysis,
        metadata=metadata or {},
    )


def _control_result(
    control_id: str,
    expected: str,
    actual: str,
    domain: ControlDomain,
    metadata: dict | None = None,
) -> ControlResult:
    expected_amount = _decimal(expected)
    actual_amount = _decimal(actual)
    return ControlResult(
        control_id=control_id,
        domain=domain,
        entity_id="entity-a",
        period_start=START,
        period_end=START + timedelta(hours=1),
        expected_amount=expected_amount,
        actual_amount=actual_amount,
        residual_amount=actual_amount - expected_amount,
        currency="INR",
        status=ControlStatus.PASS if actual_amount == expected_amount else ControlStatus.FAIL,
        tolerance=Decimal("0"),
        explanation="synthetic control result",
        metadata=metadata or {},
    )


def _event(
    event_id: str,
    event_type: EventType,
    amount: str,
    *,
    source_id: str | None = None,
    timestamp: datetime = START,
) -> FinancialEvent:
    return FinancialEvent(
        event_id=event_id,
        event_type=event_type,
        source_system="synthetic",
        source_id=source_id or event_id,
        entity_id="entity-a",
        account_id="account-a",
        merchant_id="merchant-a",
        partner_id="partner-a",
        amount=_decimal(amount),
        currency="INR",
        event_timestamp=timestamp,
        effective_timestamp=timestamp,
        status="POSTED",
    )


def _decimal(value: str) -> Decimal:
    return Decimal(value)


def _residual(residual_id: str, amount: Decimal) -> ResidualObservation:
    return ResidualObservation(
        residual_id=residual_id,
        control_id="synthetic-residual",
        domain=ControlDomain.SETTLEMENT,
        timestamp=START,
        expected_amount=Decimal("0"),
        actual_amount=amount,
        residual_amount=amount,
        currency="INR",
        status=ControlStatus.PASS if amount == 0 else ControlStatus.FAIL,
    )