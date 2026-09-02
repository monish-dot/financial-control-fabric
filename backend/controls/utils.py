"""Shared deterministic event-selection and result helpers."""

from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from backend.controls.base import determine_status
from backend.controls.models import ControlContext, ControlDomain, ControlResult
from backend.models.financial_event import EventType, FinancialEvent


def events_in_scope(
    events: Iterable[FinancialEvent],
    context: ControlContext,
    *,
    entity_id: str | None = None,
    account_id: str | None = None,
    merchant_id: str | None = None,
    partner_id: str | None = None,
) -> list[FinancialEvent]:
    """Select a period/scope and reject mixed currencies."""

    scoped: list[FinancialEvent] = []
    for event in events:
        effective_timestamp = _as_utc(event.effective_timestamp)
        if not (
            _as_utc(context.period_start)
            <= effective_timestamp
            <= _as_utc(context.period_end)
        ):
            continue
        if entity_id is not None and event.entity_id != entity_id:
            continue
        if account_id is not None and event.account_id != account_id:
            continue
        if merchant_id is not None and event.merchant_id != merchant_id:
            continue
        if partner_id is not None and event.partner_id != partner_id:
            continue
        scoped.append(event)

    mismatched = [event.currency for event in scoped if event.currency != context.currency]
    if mismatched:
        currencies = sorted({context.currency, *mismatched})
        raise ValueError(
            "multiple currencies cannot be aggregated: " + ", ".join(currencies)
        )
    return scoped


def sum_event_amounts(
    events: Iterable[FinancialEvent],
    *event_types: EventType,
) -> Decimal:
    """Sum event amounts exactly using Decimal."""

    allowed = set(event_types)
    return sum(
        (event.amount for event in events if event.event_type in allowed),
        Decimal("0"),
    )


def make_result(
    *,
    control_id: str,
    domain: ControlDomain,
    context: ControlContext,
    expected_amount: Decimal,
    actual_amount: Decimal,
    explanation: str,
    metadata: dict[str, Any],
) -> ControlResult:
    """Build a validated result from deterministic expected/actual values."""

    residual = actual_amount - expected_amount
    return ControlResult(
        control_id=context.control_id or control_id,
        domain=domain,
        entity_id=context.entity_id,
        period_start=context.period_start,
        period_end=context.period_end,
        expected_amount=expected_amount,
        actual_amount=actual_amount,
        residual_amount=residual,
        currency=context.currency,
        status=determine_status(residual, context.tolerance),
        tolerance=context.tolerance,
        explanation=explanation,
        metadata=metadata,
    )


def _as_utc(value: datetime) -> datetime:
    """Compare naive and aware timestamps consistently without changing events."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)