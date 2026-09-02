"""Nodal/escrow balance invariant."""

from collections.abc import Sequence

from backend.controls.models import (
    ControlDomain,
    ControlResult,
    NodalEscrowContext,
)
from backend.controls.utils import events_in_scope, make_result, sum_event_amounts
from backend.models.financial_event import EventType, FinancialEvent


class NodalEscrowControl:
    """Evaluate the expected escrow closing balance against a bank balance."""

    control_id = "nodal_escrow_balance"
    domain = ControlDomain.NODAL_ESCROW

    def evaluate(
        self, events: Sequence[FinancialEvent], context: NodalEscrowContext
    ) -> ControlResult:
        scoped = events_in_scope(events, context, account_id=context.account_id)
        collections = sum_event_amounts(scoped, EventType.PAYMENT)
        adjustments = sum_event_amounts(scoped, EventType.ADJUSTMENT)
        payouts = sum_event_amounts(scoped, EventType.PAYOUT)
        refunds = sum_event_amounts(scoped, EventType.REFUND)
        bank_credits = sum_event_amounts(scoped, EventType.BANK_CREDIT)
        bank_debits = sum_event_amounts(scoped, EventType.BANK_DEBIT)

        expected = (
            context.opening_balance
            + collections
            + adjustments
            - payouts
            - refunds
            - context.permitted_deductions
        )
        actual = (
            context.actual_bank_balance
            if context.actual_bank_balance is not None
            else context.opening_balance + bank_credits - bank_debits
        )
        return make_result(
            control_id=self.control_id,
            domain=self.domain,
            context=context,
            expected_amount=expected,
            actual_amount=actual,
            explanation=(
                "Expected closing balance equals opening balance plus "
                "collections and valid adjustments less payouts, refunds, "
                "and permitted deductions."
            ),
            metadata={
                "account_id": context.account_id,
                "collections": collections,
                "valid_adjustments": adjustments,
                "merchant_payouts": payouts,
                "refunds": refunds,
                "permitted_deductions": context.permitted_deductions,
                "bank_credits": bank_credits,
                "bank_debits": bank_debits,
                "event_count": len(scoped),
            },
        )