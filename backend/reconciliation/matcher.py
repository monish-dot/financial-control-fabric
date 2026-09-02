"""Deterministic candidate graph construction."""

from collections.abc import Sequence

from backend.reconciliation.models import ReconciliationConstraints, ReconciliationItem
from backend.reconciliation.scoring import CompatibilityScore, CompatibilityScorer


class CandidateMatcher:
    """Build a sorted many-to-many compatibility graph."""

    def __init__(self, scorer: CompatibilityScorer | None = None) -> None:
        self._scorer = scorer or CompatibilityScorer()

    def candidates(
        self,
        internal_items: Sequence[ReconciliationItem],
        external_items: Sequence[ReconciliationItem],
        constraints: ReconciliationConstraints,
    ) -> list[tuple[ReconciliationItem, ReconciliationItem, CompatibilityScore]]:
        candidates: list[
            tuple[ReconciliationItem, ReconciliationItem, CompatibilityScore]
        ] = []
        for internal in sorted(internal_items, key=lambda item: item.item_id):
            for external in sorted(external_items, key=lambda item: item.item_id):
                compatibility = self._scorer.score(internal, external, constraints)
                if compatibility is not None:
                    candidates.append((internal, external, compatibility))
        return sorted(
            candidates,
            key=lambda candidate: (
                -candidate[2].score,
                candidate[0].item_id,
                candidate[1].item_id,
            ),
        )