"""Merchant payout entitlement control."""

from collections.abc import Sequence

from backend.controls.models import ControlDomain, ControlResult, MerchantPayoutContext
from backend.controls.utils import events_in_scope, make_result, sum_event_amounts
from backend.models.financial_event import EventType, FinancialEvent


class MerchantPayoutControl:
    """Compare merchant entitlement less deductions with actual payouts."""

    control_id = "merchant_payout_entitlement"
    domain = ControlDomain.MERCHANT_PAYOUT

    def evaluate(
        self, events: Sequence[FinancialEvent], context: MerchantPayoutContext
    ) -> ControlResult:
        scoped = events_in_scope(events, context, merchant_id=context.merchant_id)
        entitlement = sum_event_amounts(scoped, EventType.PAYMENT)
        fees = sum_event_amounts(scoped, EventType.FEE)
        taxes = sum_event_amounts(scoped, EventType.TAX)
        refunds = sum_event_amounts(scoped, EventType.REFUND)
        adjustments = sum_event_amounts(scoped, EventType.ADJUSTMENT)
        actual = sum_event_amounts(scoped, EventType.PAYOUT)
        expected = entitlement - fees - taxes - refunds - adjustments
        return make_result(
            control_id=self.control_id,
            domain=self.domain,
            context=context,
            expected_amount=expected,
            actual_amount=actual,
            explanation=(
                "Expected merchant payout equals payment entitlement less "
                "fees, taxes, refunds, and adjustments."
            ),
            metadata={
                "merchant_id": context.merchant_id,
                "merchant_entitlement": entitlement,
                "fees": fees,
                "taxes": taxes,
                "refunds": refunds,
                "adjustments": adjustments,
                "actual_payouts": actual,
                "event_count": len(scoped),
            },
        )