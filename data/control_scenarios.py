"""Deterministic synthetic scenarios for the Phase 2 control kernel."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.controls.base import FinancialControl
from backend.controls.cross_entity import CrossEntityControl
from backend.controls.merchant_payout import MerchantPayoutControl
from backend.controls.models import (
    ControlContext,
    ControlStatus,
    CrossEntityContext,
    MerchantPayoutContext,
    NodalEscrowContext,
    RevenueRecognitionContext,
    SettlementContext,
)
from backend.controls.nodal_escrow import NodalEscrowControl
from backend.controls.revenue_recognition import RevenueRecognitionControl
from backend.controls.settlement import SettlementControl
from backend.models.financial_event import EventType, FinancialEvent


PERIOD_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
PERIOD_END = PERIOD_START + timedelta(days=31)


@dataclass(frozen=True)
class ControlScenario:
    """Known-input control scenario with a known expected outcome."""

    name: str
    control: FinancialControl
    events: tuple[FinancialEvent, ...]
    context: ControlContext
    expected_status: ControlStatus
    expected_residual: Decimal


def build_control_scenarios() -> list[ControlScenario]:
    """Build passing and failing examples for all five domains."""

    return [
        ControlScenario(
            "nodal_passing",
            NodalEscrowControl(),
            (
                _event("nodal-payment", EventType.PAYMENT, "100.00", account_id="nodal-account"),
                _event("nodal-adjustment", EventType.ADJUSTMENT, "5.00", account_id="nodal-account"),
                _event("nodal-payout", EventType.PAYOUT, "30.00", account_id="nodal-account"),
                _event("nodal-refund", EventType.REFUND, "10.00", account_id="nodal-account"),
            ),
            NodalEscrowContext(
                account_id="nodal-account",
                opening_balance=Decimal("100.00"),
                actual_bank_balance=Decimal("165.00"),
                **_scope(),
            ),
            ControlStatus.PASS,
            Decimal("0.00"),
        ),
        ControlScenario(
            "missing_transaction",
            NodalEscrowControl(),
            (
                _event("missing-payment", EventType.PAYMENT, "100.00", account_id="nodal-account"),
                _event("missing-refund", EventType.REFUND, "10.00", account_id="nodal-account"),
            ),
            NodalEscrowContext(
                account_id="nodal-account",
                opening_balance=Decimal("100.00"),
                actual_bank_balance=Decimal("170.00"),
                **_scope(),
            ),
            ControlStatus.FAIL,
            Decimal("-20.00"),
        ),
        ControlScenario(
            "bank_balance_difference",
            NodalEscrowControl(),
            (
                _event("bank-difference-payment", EventType.PAYMENT, "100.00", account_id="nodal-account"),
            ),
            NodalEscrowContext(
                account_id="nodal-account",
                opening_balance=Decimal("100.00"),
                actual_bank_balance=Decimal("199.00"),
                **_scope(),
            ),
            ControlStatus.FAIL,
            Decimal("-1.00"),
        ),
        ControlScenario(
            "settlement_passing",
            SettlementControl(),
            (
                _event("settlement-obligation", EventType.SETTLEMENT, "100.00", partner_id="partner-a"),
                _event("settlement-confirmation", EventType.BANK_CREDIT, "90.00", partner_id="partner-a"),
            ),
            SettlementContext(
                partner_id="partner-a",
                valid_timing_difference=Decimal("10.00"),
                **_scope(),
            ),
            ControlStatus.PASS,
            Decimal("0.00"),
        ),
        ControlScenario(
            "settlement_missing_confirmation",
            SettlementControl(),
            (
                _event("settlement-fail-obligation", EventType.SETTLEMENT, "100.00", partner_id="partner-a"),
                _event("settlement-fail-confirmation", EventType.BANK_CREDIT, "80.00", partner_id="partner-a"),
            ),
            SettlementContext(partner_id="partner-a", **_scope()),
            ControlStatus.FAIL,
            Decimal("-20.00"),
        ),
        ControlScenario(
            "merchant_payout_passing",
            MerchantPayoutControl(),
            (
                _event("merchant-payment", EventType.PAYMENT, "100.00"),
                _event("merchant-fee", EventType.FEE, "10.00"),
                _event("merchant-tax", EventType.TAX, "5.00"),
                _event("merchant-refund", EventType.REFUND, "15.00"),
                _event("merchant-payout", EventType.PAYOUT, "70.00"),
            ),
            MerchantPayoutContext(merchant_id="merchant-a", **_scope()),
            ControlStatus.PASS,
            Decimal("0.00"),
        ),
        ControlScenario(
            "fee_difference",
            MerchantPayoutControl(),
            (
                _event("fee-payment", EventType.PAYMENT, "100.00"),
                _event("fee-fee", EventType.FEE, "10.00"),
                _event("fee-tax", EventType.TAX, "5.00"),
                _event("fee-refund", EventType.REFUND, "15.00"),
                _event("fee-payout", EventType.PAYOUT, "80.00"),
            ),
            MerchantPayoutContext(merchant_id="merchant-a", **_scope()),
            ControlStatus.FAIL,
            Decimal("10.00"),
        ),
        ControlScenario(
            "duplicate_transaction",
            MerchantPayoutControl(),
            (
                _event("duplicate-payment", EventType.PAYMENT, "100.00"),
                _event("duplicate-fee", EventType.FEE, "10.00"),
                _event("duplicate-tax", EventType.TAX, "5.00"),
                _event("duplicate-refund", EventType.REFUND, "15.00"),
                _event("duplicate-payout-a", EventType.PAYOUT, "70.00"),
                _event("duplicate-payout-b", EventType.PAYOUT, "70.00"),
            ),
            MerchantPayoutContext(merchant_id="merchant-a", **_scope()),
            ControlStatus.FAIL,
            Decimal("70.00"),
        ),
        ControlScenario(
            "refund_difference",
            MerchantPayoutControl(),
            (
                _event("refund-payment", EventType.PAYMENT, "100.00"),
                _event("refund-fee", EventType.FEE, "10.00"),
                _event("refund-tax", EventType.TAX, "5.00"),
                _event("refund-recorded", EventType.REFUND, "5.00"),
                _event("refund-payout", EventType.PAYOUT, "70.00"),
            ),
            MerchantPayoutContext(merchant_id="merchant-a", **_scope()),
            ControlStatus.FAIL,
            Decimal("-10.00"),
        ),
        ControlScenario(
            "revenue_passing",
            RevenueRecognitionControl(),
            (_event("revenue-recognized", EventType.REVENUE_RECOGNITION, "100.00"),),
            RevenueRecognitionContext(
                expected_recognized_revenue=Decimal("100.00"),
                **_scope(),
            ),
            ControlStatus.PASS,
            Decimal("0.00"),
        ),
        ControlScenario(
            "revenue_recognition_timing_mismatch",
            RevenueRecognitionControl(),
            (_event("revenue-timing", EventType.REVENUE_RECOGNITION, "60.00"),),
            RevenueRecognitionContext(
                expected_recognized_revenue=Decimal("100.00"),
                **_scope(),
            ),
            ControlStatus.FAIL,
            Decimal("-40.00"),
        ),
        ControlScenario(
            "cross_entity_passing",
            CrossEntityControl(),
            (
                _event(
                    "intercompany-transfer",
                    EventType.INTERCOMPANY_TRANSFER,
                    "250.00",
                    entity_id="entity-source",
                    partner_id="entity-destination",
                ),
                _event(
                    "intercompany-journal",
                    EventType.JOURNAL_ENTRY,
                    "250.00",
                    entity_id="entity-destination",
                    partner_id="entity-source",
                ),
            ),
            CrossEntityContext(
                source_entity_id="entity-source",
                destination_entity_id="entity-destination",
                **_scope(),
            ),
            ControlStatus.PASS,
            Decimal("0.00"),
        ),
        ControlScenario(
            "cross_entity_mismatch",
            CrossEntityControl(),
            (
                _event(
                    "intercompany-mismatch-transfer",
                    EventType.INTERCOMPANY_TRANSFER,
                    "250.00",
                    entity_id="entity-source",
                    partner_id="entity-destination",
                ),
                _event(
                    "intercompany-mismatch-journal",
                    EventType.JOURNAL_ENTRY,
                    "200.00",
                    entity_id="entity-destination",
                    partner_id="entity-source",
                ),
            ),
            CrossEntityContext(
                source_entity_id="entity-source",
                destination_entity_id="entity-destination",
                **_scope(),
            ),
            ControlStatus.FAIL,
            Decimal("-50.00"),
        ),
    ]


def _scope() -> dict[str, object]:
    return {
        "entity_id": "entity-a",
        "period_start": PERIOD_START,
        "period_end": PERIOD_END,
        "currency": "INR",
    }


def _event(
    event_id: str,
    event_type: EventType,
    amount: str,
    *,
    entity_id: str = "entity-a",
    account_id: str = "account-a",
    merchant_id: str = "merchant-a",
    partner_id: str | None = None,
) -> FinancialEvent:
    return FinancialEvent(
        event_id=event_id,
        event_type=event_type,
        source_system="synthetic_control_scenarios",
        source_id=event_id,
        entity_id=entity_id,
        account_id=account_id,
        merchant_id=merchant_id,
        partner_id=partner_id,
        amount=Decimal(amount),
        currency="INR",
        event_timestamp=PERIOD_START + timedelta(hours=1),
        effective_timestamp=PERIOD_START + timedelta(hours=1),
        status="posted",
        metadata={"synthetic": True},
    )