"""Validation helpers for reconciliation inputs and allocations."""

from collections.abc import Iterable
from decimal import Decimal

from backend.reconciliation.models import MatchAllocation, ReconciliationItem


def validate_items(
    internal_items: Iterable[ReconciliationItem],
    external_items: Iterable[ReconciliationItem],
) -> str:
    """Validate sides, IDs, and currency isolation before optimization."""

    internal = list(internal_items)
    external = list(external_items)
    if any(item.side.value != "INTERNAL" for item in internal):
        raise ValueError("all internal_items must have side INTERNAL")
    if any(item.side.value != "EXTERNAL" for item in external):
        raise ValueError("all external_items must have side EXTERNAL")
    all_items = internal + external
    ids = [item.item_id for item in all_items]
    if len(ids) != len(set(ids)):
        raise ValueError("reconciliation item_id values must be unique")
    currencies = {item.currency for item in all_items}
    if len(currencies) > 1:
        raise ValueError(
            "mixed currencies require separate reconciliation runs: "
            + ", ".join(sorted(currencies))
        )
    return next(iter(currencies), "INR")


def validate_allocations(
    allocations: Iterable[MatchAllocation],
    internal_items: Iterable[ReconciliationItem],
    external_items: Iterable[ReconciliationItem],
) -> None:
    """Enforce allocation capacity and currency constraints."""

    internal_by_id = {item.item_id: item for item in internal_items}
    external_by_id = {item.item_id: item for item in external_items}
    internal_totals: dict[str, Decimal] = {}
    external_totals: dict[str, Decimal] = {}
    for allocation in allocations:
        internal = internal_by_id.get(allocation.internal_item_id)
        external = external_by_id.get(allocation.external_item_id)
        if internal is None or external is None:
            raise ValueError("allocation references an unknown reconciliation item")
        if allocation.allocated_amount < 0:
            raise ValueError("negative allocations are forbidden")
        if internal.currency != external.currency or allocation.currency != internal.currency:
            raise ValueError("allocations cannot cross currencies")
        internal_totals[internal.item_id] = (
            internal_totals.get(internal.item_id, Decimal("0"))
            + allocation.allocated_amount
        )
        external_totals[external.item_id] = (
            external_totals.get(external.item_id, Decimal("0"))
            + allocation.allocated_amount
        )
    for item_id, total in internal_totals.items():
        if total > internal_by_id[item_id].amount:
            raise ValueError(f"allocation exceeds internal item '{item_id}' amount")
    for item_id, total in external_totals.items():
        if total > external_by_id[item_id].amount:
            raise ValueError(f"allocation exceeds external item '{item_id}' amount")