"""In-memory audit trail for bounded investigation references."""

from datetime import datetime

from backend.agent.models import AgentAuditEvent, AuditActor


class AgentAuditTrail:
    """Record every controller step without storing sensitive database dumps."""

    def __init__(self) -> None:
        self._events: dict[str, list[AgentAuditEvent]] = {}

    def record(
        self,
        investigation_id: str,
        *,
        timestamp: datetime,
        actor: AuditActor,
        action: str,
        input_summary: str,
        output_summary: str,
        tool_name: str | None = None,
        evidence_ids: list[str] | None = None,
        calculation_ids: list[str] | None = None,
    ) -> AgentAuditEvent:
        events = self._events.setdefault(investigation_id, [])
        event = AgentAuditEvent(
            audit_id=f"{investigation_id}_audit_{len(events) + 1:04d}",
            investigation_id=investigation_id,
            timestamp=timestamp,
            actor=actor,
            action=action,
            tool_name=tool_name,
            input_summary=input_summary,
            output_summary=output_summary,
            evidence_ids=evidence_ids or [],
            calculation_ids=calculation_ids or [],
        )
        events.append(event)
        return event

    def list(self, investigation_id: str) -> list[AgentAuditEvent]:
        return list(self._events.get(investigation_id, []))