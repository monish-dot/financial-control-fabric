"""Tests for the deterministic Phase 2 financial control kernel."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.controls import ControlDomain, ControlStatus, build_default_registry
from backend.controls.merchant_payout import MerchantPayoutControl
from backend.controls.models import MerchantPayoutContext, NodalEscrowContext
from backend.models.financial_event import EventType, FinancialEvent
from data.control_scenarios import PERIOD_END, PERIOD_START, build_control_scenarios


def test_all_control_scenarios_have_known_results() -> None:
    for scenario in build_control_scenarios():
        result = scenario.control.evaluate(scenario.events, scenario.context)

        assert result.status is scenario.expected_status, scenario.name
        assert result.residual_amount == scenario.expected_residual, scenario.name


def test_nodal_control_pass() -> None:
    scenario = next(
        scenario for scenario in build_control_scenarios() if scenario.name == "nodal_passing"
    )

    result = scenario.control.evaluate(scenario.events, scenario.context)

    assert result.status is ControlStatus.PASS
    assert result.expected_amount == Decimal("165.00")
    assert result.actual_amount == Decimal("165.00")


def test_nodal_control_fail() -> None:
    scenario = next(
        scenario for scenario in build_control_scenarios() if scenario.name == "bank_balance_difference"
    )

    assert scenario.control.evaluate(scenario.events, scenario.context).status is ControlStatus.FAIL


def test_settlement_control_pass_and_fail() -> None:
    scenarios = {
        scenario.name: scenario
        for scenario in build_control_scenarios()
        if scenario.name in {"settlement_passing", "settlement_missing_confirmation"}
    }

    assert scenarios["settlement_passing"].control.evaluate(
        scenarios["settlement_passing"].events, scenarios["settlement_passing"].context
    ).status is ControlStatus.PASS
    assert scenarios["settlement_missing_confirmation"].control.evaluate(
        scenarios["settlement_missing_confirmation"].events,
        scenarios["settlement_missing_confirmation"].context,
    ).status is ControlStatus.FAIL


def test_merchant_payout_control_pass_and_fail() -> None:
    scenarios = build_control_scenarios()
    passing = next(scenario for scenario in scenarios if scenario.name == "merchant_payout_passing")
    failing = next(scenario for scenario in scenarios if scenario.name == "fee_difference")

    assert passing.control.evaluate(passing.events, passing.context).status is ControlStatus.PASS
    assert failing.control.evaluate(failing.events, failing.context).status is ControlStatus.FAIL


def test_revenue_recognition_control_pass_and_fail() -> None:
    scenarios = build_control_scenarios()
    passing = next(scenario for scenario in scenarios if scenario.name == "revenue_passing")
    failing = next(
        scenario
        for scenario in scenarios
        if scenario.name == "revenue_recognition_timing_mismatch"
    )

    assert passing.control.evaluate(passing.events, passing.context).status is ControlStatus.PASS
    assert failing.control.evaluate(failing.events, failing.context).status is ControlStatus.FAIL


def test_cross_entity_control_pass_and_fail() -> None:
    scenarios = build_control_scenarios()
    passing = next(scenario for scenario in scenarios if scenario.name == "cross_entity_passing")
    failing = next(scenario for scenario in scenarios if scenario.name == "cross_entity_mismatch")

    assert passing.control.evaluate(passing.events, passing.context).status is ControlStatus.PASS
    assert failing.control.evaluate(failing.events, failing.context).status is ControlStatus.FAIL


def test_decimal_arithmetic_is_exact() -> None:
    event = _event("decimal-payment", EventType.PAYMENT, "0.10")
    fee = _event("decimal-fee", EventType.FEE, "0.20")
    payout = _event("decimal-payout", EventType.PAYOUT, "0.30")
    context = MerchantPayoutContext(
        merchant_id="merchant-a",
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        currency="INR",
    )

    result = MerchantPayoutControl().evaluate([event, fee, payout], context)

    assert result.expected_amount == Decimal("0.10") - Decimal("0.20")
    assert result.actual_amount == Decimal("0.30")
    assert result.residual_amount == Decimal("0.40")


def test_tolerance_handling() -> None:
    context = NodalEscrowContext(
        opening_balance=Decimal("100.00"),
        actual_bank_balance=Decimal("100.01"),
        tolerance=Decimal("0.01"),
        account_id="account-a",
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        currency="INR",
    )

    result = build_default_registry().get(ControlDomain.NODAL_ESCROW).evaluate([], context)

    assert result.residual_amount == Decimal("0.01")
    assert result.status is ControlStatus.PASS


def test_control_registry() -> None:
    registry = build_default_registry()

    assert registry.get("nodal_escrow").domain is ControlDomain.NODAL_ESCROW
    assert set(registry.domains()) == set(ControlDomain)


def test_empty_event_set_is_deterministic() -> None:
    context = NodalEscrowContext(
        opening_balance=Decimal("0"),
        actual_bank_balance=Decimal("0"),
        account_id="account-a",
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        currency="INR",
    )

    result = build_default_registry().get(ControlDomain.NODAL_ESCROW).evaluate([], context)

    assert result.status is ControlStatus.PASS
    assert result.expected_amount == Decimal("0")
    assert result.actual_amount == Decimal("0")


def test_multiple_currencies_are_not_silently_aggregated() -> None:
    inr_event = _event("inr-event", EventType.PAYMENT, "100.00", currency="INR")
    usd_event = _event("usd-event", EventType.PAYMENT, "100.00", currency="USD")
    context = MerchantPayoutContext(
        merchant_id="merchant-a",
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        currency="INR",
    )

    with pytest.raises(ValueError, match="multiple currencies"):
        MerchantPayoutControl().evaluate([inr_event, usd_event], context)


def _event(
    event_id: str,
    event_type: EventType,
    amount: str,
    *,
    currency: str = "INR",
) -> FinancialEvent:
    timestamp = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    return FinancialEvent(
        event_id=event_id,
        event_type=event_type,
        source_system="synthetic_tests",
        source_id=event_id,
        entity_id="entity-a",
        account_id="account-a",
        merchant_id="merchant-a",
        amount=Decimal(amount),
        currency=currency,
        event_timestamp=timestamp,
        effective_timestamp=timestamp,
        status="posted",
    )