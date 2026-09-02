"""Common interface and helpers for deterministic controls."""

from collections.abc import Sequence
from decimal import Decimal
from typing import Protocol

from backend.controls.models import ControlContext, ControlDomain, ControlResult, ControlStatus
from backend.models.financial_event import FinancialEvent


class FinancialControl(Protocol):
    """Interface implemented by every financial control."""

    control_id: str
    domain: ControlDomain

    def evaluate(
        self, events: Sequence[FinancialEvent], context: ControlContext
    ) -> ControlResult:
        """Evaluate the control against a scoped event collection."""


def determine_status(residual: Decimal, tolerance: Decimal) -> ControlStatus:
    """Determine status without floating-point arithmetic or model inference."""

    return (
        ControlStatus.PASS
        if abs(residual) <= tolerance
        else ControlStatus.FAIL
    )