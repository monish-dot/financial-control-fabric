"""Deterministic revenue recognition control."""

from collections.abc import Sequence

from backend.controls.models import ControlDomain, ControlResult, RevenueRecognitionContext
from backend.controls.utils import events_in_scope, make_result, sum_event_amounts
from backend.models.financial_event import EventType, FinancialEvent


class RevenueRecognitionControl:
    """Compare a supplied recognition schedule with recorded recognition events."""

    control_id = "revenue_recognition_schedule"
    domain = ControlDomain.REVENUE_RECOGNITION

    def evaluate(
        self, events: Sequence[FinancialEvent], context: RevenueRecognitionContext
    ) -> ControlResult:
        scoped = events_in_scope(events, context, entity_id=context.entity_id)
        actual = sum_event_amounts(scoped, EventType.REVENUE_RECOGNITION)
        return make_result(
            control_id=self.control_id,
            domain=self.domain,
            context=context,
            expected_amount=context.expected_recognized_revenue,
            actual_amount=actual,
            explanation=(
                "Expected recognized revenue is supplied by the deterministic "
                "recognition schedule and compared with recorded recognition events."
            ),
            metadata={
                "expected_recognized_revenue": context.expected_recognized_revenue,
                "recorded_revenue_recognition": actual,
                "event_count": len(scoped),
            },
        )