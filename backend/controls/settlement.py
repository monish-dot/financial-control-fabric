"""Aggregate multi-bank/multi-partner settlement obligation control."""

from collections.abc import Sequence

from backend.controls.models import ControlDomain, ControlResult, SettlementContext
from backend.controls.utils import events_in_scope, make_result, sum_event_amounts
from backend.models.financial_event import EventType, FinancialEvent


class SettlementControl:
    """Compare aggregate settlement obligations with confirmations."""

    control_id = "multi_bank_partner_settlement"
    domain = ControlDomain.SETTLEMENT

    def evaluate(
        self, events: Sequence[FinancialEvent], context: SettlementContext
    ) -> ControlResult:
        scoped = events_in_scope(
            events,
            context,
            entity_id=context.entity_id,
            account_id=context.account_id,
            partner_id=context.partner_id,
        )
        obligations = sum_event_amounts(scoped, EventType.SETTLEMENT)
        confirmations = (
            sum_event_amounts(scoped, EventType.BANK_CREDIT)
            - sum_event_amounts(scoped, EventType.BANK_DEBIT)
        )
        adjustments = sum_event_amounts(scoped, EventType.ADJUSTMENT)
        actual = confirmations + context.valid_timing_difference + adjustments
        return make_result(
            control_id=self.control_id,
            domain=self.domain,
            context=context,
            expected_amount=obligations,
            actual_amount=actual,
            explanation=(
                "Aggregate settlement obligations are compared with bank or "
                "partner confirmations, valid timing differences, and adjustments."
            ),
            metadata={
                "partner_id": context.partner_id,
                "internal_settlement_obligations": obligations,
                "settlement_confirmations": confirmations,
                "valid_timing_difference": context.valid_timing_difference,
                "valid_adjustments": adjustments,
                "event_count": len(scoped),
            },
        )