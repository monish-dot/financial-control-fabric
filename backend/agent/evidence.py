"""Evidence construction from bounded tool results."""

from decimal import Decimal

from backend.agent.models import EvidenceItem, ToolResult


def evidence_from_tool_result(
    result: ToolResult,
    *,
    investigation_id: str,
    relevance: Decimal = Decimal("1"),
) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            evidence_id=f"{investigation_id}_evidence_{index + 1:04d}",
            source_type=event.event_type.value,
            source_id=event.event_id,
            field="amount",
            value=event.amount,
            timestamp=event.event_timestamp,
            relevance=relevance,
            metadata={
                "tool_name": result.tool_name,
                "currency": event.currency,
                "reference_id": event.source_id,
            },
        )
        for index, event in enumerate(result.items)
    ]