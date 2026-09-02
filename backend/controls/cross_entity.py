"""Cross-entity intercompany reconciliation control."""

from collections.abc import Sequence

from backend.controls.models import ControlDomain, ControlResult, CrossEntityContext
from backend.controls.utils import events_in_scope, make_result, sum_event_amounts
from backend.models.financial_event import EventType, FinancialEvent


class CrossEntityControl:
    """Compare source-side transfers with destination-side journal entries."""

    control_id = "cross_entity_intercompany"
    domain = ControlDomain.CROSS_ENTITY

    def evaluate(
        self, events: Sequence[FinancialEvent], context: CrossEntityContext
    ) -> ControlResult:
        scoped = events_in_scope(events, context)
        source_events = [
            event
            for event in scoped
            if event.entity_id == context.source_entity_id
            and event.event_type is EventType.INTERCOMPANY_TRANSFER
            and _has_counterparty(event, context.destination_entity_id)
        ]
        destination_events = [
            event
            for event in scoped
            if event.entity_id == context.destination_entity_id
            and event.event_type is EventType.JOURNAL_ENTRY
            and _has_counterparty(event, context.source_entity_id)
        ]
        expected = sum_event_amounts(source_events, EventType.INTERCOMPANY_TRANSFER)
        actual = sum_event_amounts(destination_events, EventType.JOURNAL_ENTRY)
        return make_result(
            control_id=self.control_id,
            domain=self.domain,
            context=context,
            expected_amount=expected,
            actual_amount=actual,
            explanation=(
                "Source-entity intercompany transfers are compared with "
                "destination-entity corresponding journal entries."
            ),
            metadata={
                "source_entity_id": context.source_entity_id,
                "destination_entity_id": context.destination_entity_id,
                "source_transfer_amount": expected,
                "destination_journal_amount": actual,
                "source_event_count": len(source_events),
                "destination_event_count": len(destination_events),
            },
        )


def _has_counterparty(event: FinancialEvent, entity_id: str) -> bool:
    """Match explicit partner or metadata counterparty identifiers."""

    return entity_id in (
        event.partner_id,
        event.metadata.get("counterparty_entity_id"),
        event.metadata.get("source_entity_id"),
        event.metadata.get("destination_entity_id"),
    )