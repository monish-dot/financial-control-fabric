"""Human approval boundary for controller recommendations."""

from datetime import datetime

from backend.agent.models import (
    ApprovalStatus,
    AuditActor,
    ControllerAction,
    Recommendation,
)


def create_pending_action(
    investigation_id: str,
    recommendation: Recommendation,
) -> ControllerAction:
    return ControllerAction(
        action_id=f"{investigation_id}_action",
        investigation_id=investigation_id,
        action_type=recommendation.category,
        description=recommendation.description,
        proposed_by=AuditActor.AGENT,
        requires_approval=True,
        approval_status=ApprovalStatus.PENDING,
    )


def record_explicit_approval(
    action: ControllerAction,
    *,
    approved: bool,
    approved_by: str,
    approved_at: datetime,
) -> ControllerAction:
    if not approved_by.strip():
        raise ValueError("approved_by is required")
    return action.model_copy(
        update={
            "approval_status": (
                ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            ),
            "approved_by": approved_by,
            "approved_at": approved_at,
        }
    )