"""Reconciliation service and residual-intelligence integration point."""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from hashlib import sha256

from backend.anomaly.residual_models import ResidualObservation
from backend.controls.models import ControlDomain, ControlStatus
from backend.reconciliation.constraints import validate_items
from backend.reconciliation.models import (
    ReconciliationConstraints,
    ReconciliationItem,
    ReconciliationResult,
    ReconciliationStatus,
)
from backend.reconciliation.optimizer import AllocationOptimizer


class ReconciliationService:
    """Run and retain proposed reconciliation results in memory."""

    def __init__(self, optimizer: AllocationOptimizer | None = None) -> None:
        self._optimizer = optimizer or AllocationOptimizer()
        self._results: dict[str, ReconciliationResult] = {}

    def reconcile(
        self,
        internal_items: Sequence[ReconciliationItem],
        external_items: Sequence[ReconciliationItem],
        constraints: ReconciliationConstraints | None = None,
        *,
        reconciliation_id: str | None = None,
    ) -> ReconciliationResult:
        constraints = constraints or ReconciliationConstraints()
        currency = validate_items(internal_items, external_items)
        allocations = self._optimizer.optimize(
            internal_items, external_items, constraints
        )
        matched = sum(
            (allocation.allocated_amount for allocation in allocations),
            Decimal("0"),
        )
        internal_total = sum(
            (item.amount for item in internal_items), Decimal("0")
        )
        external_total = sum(
            (item.amount for item in external_items), Decimal("0")
        )
        unmatched_internal = internal_total - matched
        unmatched_external = external_total - matched
        if internal_total == 0 and external_total == 0:
            match_rate = Decimal("1")
        elif internal_total == 0:
            match_rate = Decimal("0")
        else:
            match_rate = matched / internal_total
        if internal_total == 0 and external_total == 0:
            reconciliation_status = ReconciliationStatus.FULLY_RECONCILED
        elif matched == 0:
            reconciliation_status = ReconciliationStatus.UNRECONCILED
        elif unmatched_internal == 0 and unmatched_external == 0:
            reconciliation_status = ReconciliationStatus.FULLY_RECONCILED
        else:
            reconciliation_status = ReconciliationStatus.PARTIALLY_RECONCILED
        result = ReconciliationResult(
            reconciliation_id=reconciliation_id
            or _reconciliation_id(internal_items, external_items, constraints),
            matched_amount=matched,
            unmatched_internal_amount=unmatched_internal,
            unmatched_external_amount=unmatched_external,
            allocation_count=len(allocations),
            match_rate=match_rate,
            currency=currency,
            status=reconciliation_status,
            allocations=allocations,
            explanation=_explanation(
                matched,
                unmatched_internal,
                len(internal_items),
                len(external_items),
                reconciliation_status,
            ),
            metadata={
                "internal_item_count": len(internal_items),
                "external_item_count": len(external_items),
                "constraints": constraints.model_dump(mode="json"),
                "optimizer": "ortools_cp_sat" if _ortools_available() else "deterministic_fallback",
            },
        )
        self._results[result.reconciliation_id] = result
        return result

    def get_reconciliation(self, reconciliation_id: str) -> ReconciliationResult | None:
        return self._results.get(reconciliation_id)

    def to_residual_observation(
        self,
        result: ReconciliationResult,
        *,
        residual_id: str,
        control_id: str,
        domain: ControlDomain,
        timestamp: datetime,
        entity_id: str | None = None,
        account_id: str | None = None,
        merchant_id: str | None = None,
        partner_id: str | None = None,
    ) -> ResidualObservation:
        """Adapt a result for the existing residual-intelligence layer."""

        status = (
            ControlStatus.PASS
            if result.status is ReconciliationStatus.FULLY_RECONCILED
            else ControlStatus.FAIL
        )
        return ResidualObservation(
            residual_id=residual_id,
            control_id=control_id,
            domain=domain,
            entity_id=entity_id,
            account_id=account_id,
            merchant_id=merchant_id,
            partner_id=partner_id,
            timestamp=timestamp,
            expected_amount=result.unmatched_internal_amount,
            actual_amount=result.unmatched_external_amount,
            residual_amount=(
                result.unmatched_external_amount
                - result.unmatched_internal_amount
            ),
            currency=result.currency,
            status=status,
            metadata={
                "reconciliation_id": result.reconciliation_id,
                "matched_amount": result.matched_amount,
                "reconciliation_status": result.status.value,
            },
        )


def _reconciliation_id(
    internal_items: Sequence[ReconciliationItem],
    external_items: Sequence[ReconciliationItem],
    constraints: ReconciliationConstraints,
) -> str:
    internal_ids = ",".join(sorted(item.item_id for item in internal_items))
    external_ids = ",".join(sorted(item.item_id for item in external_items))
    signature = (
        f"{internal_ids or 'none'}|{external_ids or 'none'}|"
        f"{constraints.model_dump_json()}"
    ).encode()
    digest = sha256(signature).hexdigest()[:16]
    return f"recon_{digest}"


def _explanation(
    matched: Decimal,
    unmatched_internal: Decimal,
    internal_count: int,
    external_count: int,
    status: ReconciliationStatus,
) -> str:
    if status is ReconciliationStatus.FULLY_RECONCILED:
        return (
            f"{matched} matched across {internal_count} internal obligations "
            f"and {external_count} external settlements. All allocation "
            "capacity constraints satisfied."
        )
    if status is ReconciliationStatus.PARTIALLY_RECONCILED:
        return f"{matched} matched. {unmatched_internal} internal obligation remains unmatched."
    return "No valid allocation satisfied the configured reconciliation constraints."


def _ortools_available() -> bool:
    from backend.reconciliation.optimizer import cp_model

    return cp_model is not None