"""Explainable deterministic compatibility scoring."""

import re
from datetime import timedelta
from decimal import Decimal

from backend.reconciliation.models import (
    MatchAllocation,
    ReconciliationConstraints,
    ReconciliationItem,
)


class CompatibilityScore:
    """Compatibility score and explanation for one candidate pair."""

    def __init__(
        self,
        score: Decimal,
        reason: str,
        metadata: dict[str, object],
    ) -> None:
        self.score = score
        self.reason = reason
        self.metadata = metadata


class CompatibilityScorer:
    """Score candidate pairs without embeddings or learned behavior."""

    def score(
        self,
        internal: ReconciliationItem,
        external: ReconciliationItem,
        constraints: ReconciliationConstraints,
    ) -> CompatibilityScore | None:
        if internal.currency != external.currency:
            return None
        checks = (
            ("entity", internal.entity_id, external.entity_id, constraints.require_entity_match),
            ("account", internal.account_id, external.account_id, constraints.require_account_match),
            ("merchant", internal.merchant_id, external.merchant_id, constraints.require_merchant_match),
            ("partner", internal.partner_id, external.partner_id, constraints.require_partner_match),
        )
        for label, left, right, required in checks:
            if required and left != right:
                return None

        reference_match = _reference_matches(
            internal.reference_id,
            external.reference_id,
            constraints.normalize_references,
        )
        if constraints.require_reference_match and not reference_match:
            return None

        timestamp_difference = _seconds_between(internal.timestamp, external.timestamp)
        if (
            constraints.timestamp_tolerance_minutes is not None
            and timestamp_difference
            > constraints.timestamp_tolerance_minutes * 60
        ):
            return None

        amount_similarity = _amount_similarity(internal.amount, external.amount)
        entity_score = _field_score(internal.entity_id, external.entity_id)
        account_score = _field_score(internal.account_id, external.account_id)
        merchant_score = _field_score(internal.merchant_id, external.merchant_id)
        partner_score = _field_score(internal.partner_id, external.partner_id)
        reference_score = Decimal("1") if reference_match else Decimal("0")
        timestamp_score = _timestamp_score(
            timestamp_difference, constraints.timestamp_tolerance_minutes
        )
        score = (
            amount_similarity
            + entity_score
            + account_score
            + merchant_score
            + partner_score
            + reference_score
            + timestamp_score
            + Decimal("1")
        ) / Decimal("8")
        if score < constraints.minimum_compatibility_score:
            return None

        reason_parts = ["currency equal"]
        if amount_similarity == Decimal("1"):
            reason_parts.append("amount equal")
        if reference_match:
            reason_parts.append("reference normalized match")
        for label, left, right, _ in checks:
            if left is not None and left == right:
                reason_parts.append(f"{label} compatible")
        if timestamp_difference == 0:
            reason_parts.append("timestamp equal")
        elif constraints.timestamp_tolerance_minutes is not None:
            reason_parts.append(
                f"timestamp difference {timestamp_difference} seconds"
            )
        return CompatibilityScore(
            score=score,
            reason="; ".join(reason_parts),
            metadata={
                "amount_similarity": amount_similarity,
                "reference_match": reference_match,
                "timestamp_difference_seconds": Decimal(str(timestamp_difference)),
                "entity_compatibility": entity_score,
                "account_compatibility": account_score,
                "merchant_compatibility": merchant_score,
                "partner_compatibility": partner_score,
                "currency_equality": True,
            },
        )


def allocation_from_candidate(
    *,
    allocation_id: str,
    internal: ReconciliationItem,
    external: ReconciliationItem,
    allocated_amount: Decimal,
    compatibility: CompatibilityScore,
) -> MatchAllocation:
    return MatchAllocation(
        allocation_id=allocation_id,
        internal_item_id=internal.item_id,
        external_item_id=external.item_id,
        allocated_amount=allocated_amount,
        currency=internal.currency,
        confidence=compatibility.score,
        reason=compatibility.reason,
        constraints_satisfied=True,
        metadata=compatibility.metadata,
    )


def normalize_reference(reference: str | None) -> str | None:
    """Normalize common system prefixes while preserving the reference body."""

    if reference is None:
        return None
    normalized = re.sub(r"[^A-Z0-9]", "", reference.upper())
    for prefix in ("BANK", "PARTNER", "CONFIRMATION", "SETTLEMENT"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
    return normalized


def _reference_matches(
    internal: str | None,
    external: str | None,
    normalize: bool,
) -> bool:
    if internal is None or external is None:
        return False
    if normalize:
        return normalize_reference(internal) == normalize_reference(external)
    return internal == external


def _amount_similarity(left: Decimal, right: Decimal) -> Decimal:
    if left == right:
        return Decimal("1")
    maximum = max(left, right)
    return Decimal("0") if maximum == 0 else min(left, right) / maximum


def _field_score(left: str | None, right: str | None) -> Decimal:
    if left is None or right is None:
        return Decimal("0")
    return Decimal("1") if left == right else Decimal("0")


def _timestamp_score(seconds: Decimal, tolerance_minutes: int | None) -> Decimal:
    if seconds == 0:
        return Decimal("1")
    if tolerance_minutes is None:
        return Decimal("0.5")
    window_seconds = Decimal(tolerance_minutes * 60)
    return max(Decimal("0"), Decimal("1") - seconds / window_seconds)


def _seconds_between(left, right) -> Decimal:
    difference: timedelta = abs(left - right)
    return (
        Decimal(difference.days * 86400 + difference.seconds)
        + Decimal(difference.microseconds) / Decimal("1000000")
    )