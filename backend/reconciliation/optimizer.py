"""Integer-scaled deterministic many-to-many allocation optimizer."""

from collections.abc import Sequence
from decimal import Decimal

from backend.reconciliation.constraints import validate_allocations
from backend.reconciliation.matcher import CandidateMatcher
from backend.reconciliation.models import (
    MatchAllocation,
    ReconciliationConstraints,
    ReconciliationItem,
)
from backend.reconciliation.scoring import allocation_from_candidate

try:
    from ortools.sat.python import cp_model
except ImportError:  # pragma: no cover - exercised only without optional dependency
    cp_model = None


class AllocationOptimizer:
    """Maximize valid matched amount, then compatibility score."""

    def __init__(self, matcher: CandidateMatcher | None = None) -> None:
        self._matcher = matcher or CandidateMatcher()

    def optimize(
        self,
        internal_items: Sequence[ReconciliationItem],
        external_items: Sequence[ReconciliationItem],
        constraints: ReconciliationConstraints,
    ) -> list[MatchAllocation]:
        candidates = self._matcher.candidates(
            internal_items, external_items, constraints
        )
        if not candidates:
            return []
        scale = _amount_scale(
            [item.amount for item in (*internal_items, *external_items)]
        )
        if cp_model is None:
            allocations = self._fallback(candidates, scale)
        else:
            allocations = self._cp_sat(candidates, scale)
        validate_allocations(allocations, internal_items, external_items)
        return allocations

    def _cp_sat(
        self,
        candidates,
        scale: int,
    ) -> list[MatchAllocation]:
        model = cp_model.CpModel()
        units = [
            (
                int(internal.amount * scale),
                int(external.amount * scale),
            )
            for internal, external, _ in candidates
        ]
        internal_amounts = {
            internal.item_id: int(internal.amount * scale)
            for internal, _, _ in candidates
        }
        external_amounts = {
            external.item_id: int(external.amount * scale)
            for _, external, _ in candidates
        }
        variables = [
            model.new_int_var(0, min(internal_units, external_units), f"allocation_{i}")
            for i, (internal_units, external_units) in enumerate(units)
        ]
        internal_ids = sorted({internal.item_id for internal, _, _ in candidates})
        external_ids = sorted({external.item_id for _, external, _ in candidates})
        for item_id in internal_ids:
            model.add(
                sum(
                    variable
                    for variable, (internal, _, _) in zip(variables, candidates)
                    if internal.item_id == item_id
                )
                <= internal_amounts[item_id]
            )
        for item_id in external_ids:
            model.add(
                sum(
                    variable
                    for variable, (_, external, _) in zip(variables, candidates)
                    if external.item_id == item_id
                )
                <= external_amounts[item_id]
            )

        score_scale = 1_000_000
        amount_priority = score_scale * len(candidates) + 1
        objective = sum(
            variable
            * (amount_priority + int(compatibility.score * score_scale))
            for variable, (_, _, compatibility) in zip(variables, candidates)
        )
        model.maximize(objective)
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = 0
        solver.parameters.cp_model_presolve = True
        status = solver.solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return []

        allocations: list[MatchAllocation] = []
        decimal_scale = Decimal(scale)
        for index, (variable, (internal, external, compatibility)) in enumerate(
            zip(variables, candidates)
        ):
            allocated_units = solver.value(variable)
            if allocated_units <= 0:
                continue
            allocations.append(
                allocation_from_candidate(
                    allocation_id=f"allocation_{index + 1:04d}",
                    internal=internal,
                    external=external,
                    allocated_amount=Decimal(allocated_units) / decimal_scale,
                    compatibility=compatibility,
                )
            )
        return allocations

    def _fallback(self, candidates, scale: int) -> list[MatchAllocation]:
        """Deterministic greedy fallback if OR-Tools is unavailable."""

        remaining_internal = {
            internal.item_id: int(internal.amount * scale)
            for internal, _, _ in candidates
        }
        remaining_external = {
            external.item_id: int(external.amount * scale)
            for _, external, _ in candidates
        }
        allocations: list[MatchAllocation] = []
        for index, (internal, external, compatibility) in enumerate(candidates):
            amount = min(
                remaining_internal[internal.item_id],
                remaining_external[external.item_id],
            )
            if amount <= 0:
                continue
            remaining_internal[internal.item_id] -= amount
            remaining_external[external.item_id] -= amount
            allocations.append(
                allocation_from_candidate(
                    allocation_id=f"allocation_{index + 1:04d}",
                    internal=internal,
                    external=external,
                    allocated_amount=Decimal(amount) / Decimal(scale),
                    compatibility=compatibility,
                )
            )
        return allocations


def _amount_scale(amounts: Sequence[Decimal]) -> int:
    maximum_decimal_places = max(
        (-amount.as_tuple().exponent for amount in amounts if amount.as_tuple().exponent < 0),
        default=0,
    )
    return 10**maximum_decimal_places