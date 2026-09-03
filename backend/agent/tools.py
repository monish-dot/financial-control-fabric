"""Explicit, bounded, read-only tools over canonical financial events."""

from collections.abc import Callable

from backend.agent.models import RetrievalStatus, ToolQuery, ToolResult
from backend.models.financial_event import EventType
from backend.repositories.financial_event import FinancialEventRepository


TOOL_EVENT_TYPES: dict[str, set[EventType]] = {
    "search_payments": {EventType.PAYMENT},
    "search_refunds": {EventType.REFUND},
    "search_payouts": {EventType.PAYOUT},
    "search_settlements": {EventType.SETTLEMENT},
    "search_bank_transactions": {EventType.BANK_CREDIT, EventType.BANK_DEBIT},
    "search_adjustments": {EventType.ADJUSTMENT},
    "search_revenue_records": {EventType.REVENUE_RECOGNITION},
    "search_intercompany_records": {
        EventType.INTERCOMPANY_TRANSFER,
        EventType.JOURNAL_ENTRY,
    },
}


class ReadOnlyFinancialTools:
    """Allow only named event searches; no SQL or mutation surface is exposed."""

    def __init__(self, repository: FinancialEventRepository) -> None:
        self._repository = repository

    def search_events(self, query: ToolQuery) -> ToolResult:
        return self._run("search_events", query)

    def get_event(self, event_id: str) -> ToolResult:
        if not event_id.strip():
            raise ValueError("event_id must not be empty")
        event = self._repository.get_event(event_id)
        items = [] if event is None else [event]
        return ToolResult(
            tool_name="get_event",
            items=items,
            count=len(items),
            retrieval_status=(
                RetrievalStatus.SUCCESS
                if items
                else RetrievalStatus.NO_EVIDENCE
            ),
        )

    def call(self, tool_name: str, query: ToolQuery) -> ToolResult:
        """Invoke only one of the explicitly registered read-only tools."""

        if tool_name == "get_event":
            raise ValueError("get_event requires an event ID and is not a query tool")
        if tool_name not in {"search_events", *TOOL_EVENT_TYPES}:
            raise ValueError(f"unknown read-only tool '{tool_name}'")
        return getattr(self, tool_name)(query)

    def __getattr__(self, name: str) -> Callable[[ToolQuery], ToolResult]:
        if name in TOOL_EVENT_TYPES:
            return lambda query: self._run(name, query)
        raise AttributeError(name)

    def _run(self, tool_name: str, query: ToolQuery) -> ToolResult:
        events = self._repository.list_events(
            event_types=TOOL_EVENT_TYPES.get(tool_name),
            entity_id=query.entity_id,
            account_id=query.account_id,
            merchant_id=query.merchant_id,
            partner_id=query.partner_id,
            currency=query.currency,
            period_start=query.period_start,
            period_end=query.period_end,
            reference_id=query.reference_id,
            limit=query.limit + 1,
            offset=query.offset,
        )
        truncated = len(events) > query.limit
        items = events[: query.limit]
        return ToolResult(
            tool_name=tool_name,
            items=items,
            count=len(items),
            truncated=truncated,
            retrieval_status=(
                RetrievalStatus.SUCCESS
                if items
                else RetrievalStatus.NO_EVIDENCE
            ),
        )