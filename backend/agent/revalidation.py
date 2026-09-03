"""Revalidation of a control result after an explicit approval."""

from backend.agent.models import RevalidationResult
from backend.controls.models import ControlResult, ControlStatus


def revalidate(
    previous: ControlResult,
    current: ControlResult,
) -> RevalidationResult:
    if previous.control_id != current.control_id:
        raise ValueError("revalidation control_id must match the investigation")
    if previous.currency != current.currency:
        raise ValueError("revalidation currency must match the investigation")
    resolved = current.status is ControlStatus.PASS
    return RevalidationResult(
        control_id=previous.control_id,
        previous_residual=previous.residual_amount,
        new_residual=current.residual_amount,
        previous_status=previous.status,
        new_status=current.status,
        resolved=resolved,
        explanation=(
            "The rerun control now passes; the previous residual is resolved."
            if resolved
            else "The rerun control still fails or warns; the issue remains unresolved."
        ),
    )