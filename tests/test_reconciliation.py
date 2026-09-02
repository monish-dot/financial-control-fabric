"""Tests for deterministic constrained many-to-many reconciliation."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.reconciliation.constraints import validate_allocations
from backend.reconciliation.models import (
    MatchAllocation,
    ReconciliationConstraints,
    ReconciliationItem,
    ReconciliationItemType,
    ReconciliationSide,
    ReconciliationStatus,
)
from backend.reconciliation.scoring import CompatibilityScorer
from backend.reconciliation.service import ReconciliationService


PERIOD_START = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)


def test_one_to_one_matching() -> None:
    result = _service().reconcile(
        [_item("I1", "100", ReconciliationSide.INTERNAL)],
        [_item("E1", "100", ReconciliationSide.EXTERNAL)],
    )

    assert result.status is ReconciliationStatus.FULLY_RECONCILED
    assert result.matched_amount == Decimal("100")
    assert result.match_rate == Decimal("1")
    assert len(result.allocations) == 1


def test_many_to_one_matching() -> None:
    result = _service().reconcile(
        [
            _item("I1", "100", ReconciliationSide.INTERNAL),
            _item("I2", "200", ReconciliationSide.INTERNAL),
        ],
        [_item("E1", "300", ReconciliationSide.EXTERNAL)],
    )

    assert result.matched_amount == Decimal("300")
    assert result.allocation_count == 2


def test_one_to_many_matching() -> None:
    result = _service().reconcile(
        [_item("I1", "300", ReconciliationSide.INTERNAL)],
        [
            _item("E1", "100", ReconciliationSide.EXTERNAL),
            _item("E2", "200", ReconciliationSide.EXTERNAL),
        ],
    )

    assert result.matched_amount == Decimal("300")
    assert result.allocation_count == 2


def test_many_to_many_matching_example() -> None:
    result = _service().reconcile(
        [
            _item("I1", "100", ReconciliationSide.INTERNAL),
            _item("I2", "200", ReconciliationSide.INTERNAL),
            _item("I3", "300", ReconciliationSide.INTERNAL),
        ],
        [
            _item("E1", "250", ReconciliationSide.EXTERNAL),
            _item("E2", "350", ReconciliationSide.EXTERNAL),
        ],
    )

    assert result.matched_amount == Decimal("600")
    assert result.unmatched_internal_amount == Decimal("0")
    assert result.unmatched_external_amount == Decimal("0")
    assert result.match_rate == Decimal("1")
    assert result.status is ReconciliationStatus.FULLY_RECONCILED
    assert len({item.internal_item_id for item in result.allocations}) == 3
    assert len({item.external_item_id for item in result.allocations}) == 2


def test_partial_settlement_example() -> None:
    result = _service().reconcile(
        [
            _item("I1", "100", ReconciliationSide.INTERNAL),
            _item("I2", "200", ReconciliationSide.INTERNAL),
            _item("I3", "300", ReconciliationSide.INTERNAL),
        ],
        [
            _item("E1", "250", ReconciliationSide.EXTERNAL),
            _item("E2", "200", ReconciliationSide.EXTERNAL),
        ],
    )

    assert result.matched_amount == Decimal("450")
    assert result.unmatched_internal_amount == Decimal("150")
    assert result.unmatched_external_amount == Decimal("0")
    assert result.status is ReconciliationStatus.PARTIALLY_RECONCILED
    assert result.match_rate == Decimal("0.75")


def test_full_partial_settlement_split() -> None:
    result = _service().reconcile(
        [_item("I1", "1000", ReconciliationSide.INTERNAL)],
        [
            _item("E1", "600", ReconciliationSide.EXTERNAL),
            _item("E2", "400", ReconciliationSide.EXTERNAL),
        ],
    )

    assert result.status is ReconciliationStatus.FULLY_RECONCILED
    assert result.matched_amount == Decimal("1000")


def test_duplicate_external_records_do_not_overallocate() -> None:
    result = _service().reconcile(
        [_item("I1", "500", ReconciliationSide.INTERNAL)],
        [
            _item("E1", "500", ReconciliationSide.EXTERNAL),
            _item("E2", "500", ReconciliationSide.EXTERNAL),
        ],
    )

    assert result.matched_amount == Decimal("500")
    assert result.unmatched_external_amount == Decimal("500")
    assert result.allocation_count == 1


def test_currency_isolation() -> None:
    with pytest.raises(ValueError, match="mixed currencies"):
        _service().reconcile(
            [_item("I1", "1000", ReconciliationSide.INTERNAL, currency="INR")],
            [_item("E1", "1000", ReconciliationSide.EXTERNAL, currency="USD")],
        )


def test_negative_allocation_rejected() -> None:
    with pytest.raises(ValidationError):
        MatchAllocation(
            allocation_id="A1",
            internal_item_id="I1",
            external_item_id="E1",
            allocated_amount=Decimal("-1"),
            currency="INR",
            confidence=Decimal("1"),
            reason="invalid",
            constraints_satisfied=False,
        )


def test_allocation_cannot_exceed_internal_amount() -> None:
    allocation = _allocation("150")
    with pytest.raises(ValueError, match="internal item"):
        validate_allocations(
            [allocation],
            [_item("I1", "100", ReconciliationSide.INTERNAL)],
            [_item("E1", "200", ReconciliationSide.EXTERNAL)],
        )


def test_allocation_cannot_exceed_external_amount() -> None:
    allocation = _allocation("150")
    with pytest.raises(ValueError, match="external item"):
        validate_allocations(
            [allocation],
            [_item("I1", "200", ReconciliationSide.INTERNAL)],
            [_item("E1", "100", ReconciliationSide.EXTERNAL)],
        )


def test_timestamp_tolerance_and_metadata() -> None:
    internal = _item("I1", "100", ReconciliationSide.INTERNAL)
    external = _item(
        "E1",
        "100",
        ReconciliationSide.EXTERNAL,
        timestamp=PERIOD_START + timedelta(minutes=20),
    )
    within = _service().reconcile(
        [internal],
        [external],
        ReconciliationConstraints(timestamp_tolerance_minutes=30),
    )
    outside = _service().reconcile(
        [internal],
        [external],
        ReconciliationConstraints(timestamp_tolerance_minutes=10),
    )

    assert within.matched_amount == Decimal("100")
    assert within.allocations[0].metadata["timestamp_difference_seconds"] == Decimal(
        "1200"
    )
    assert outside.status is ReconciliationStatus.UNRECONCILED


def test_reference_normalization() -> None:
    internal = _item(
        "I1", "100", ReconciliationSide.INTERNAL, reference_id="SET-1001"
    )
    external = _item(
        "E1", "100", ReconciliationSide.EXTERNAL, reference_id="BANK-SET-1001"
    )
    scorer = CompatibilityScorer()
    compatibility = scorer.score(internal, external, ReconciliationConstraints())

    assert compatibility is not None
    assert compatibility.metadata["reference_match"] is True
    assert "reference normalized match" in compatibility.reason


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("merchant_id", "merchant-a"),
        ("partner_id", "partner-a"),
        ("entity_id", "entity-a"),
    ],
)
def test_configured_dimension_compatibility(field: str, value: str) -> None:
    internal = _item("I1", "100", ReconciliationSide.INTERNAL, **{field: value})
    external = _item("E1", "100", ReconciliationSide.EXTERNAL, **{field: value})
    other = _item(
        "E2",
        "100",
        ReconciliationSide.EXTERNAL,
        **{field: f"different-{value}"},
    )
    constraints = ReconciliationConstraints(**{f"require_{field.removesuffix('_id')}_match": True})

    result = _service().reconcile([internal], [external, other], constraints)

    assert result.matched_amount == Decimal("100")
    assert result.allocations[0].external_item_id == "E1"


def test_deterministic_repeated_result() -> None:
    internal = [
        _item("I2", "200", ReconciliationSide.INTERNAL),
        _item("I1", "100", ReconciliationSide.INTERNAL),
    ]
    external = [
        _item("E2", "150", ReconciliationSide.EXTERNAL),
        _item("E1", "150", ReconciliationSide.EXTERNAL),
    ]

    first = _service().reconcile(internal, external)
    second = _service().reconcile(internal, external)

    assert first.model_dump() == second.model_dump()


def test_empty_internal_set() -> None:
    result = _service().reconcile(
        [],
        [_item("E1", "100", ReconciliationSide.EXTERNAL)],
    )

    assert result.matched_amount == Decimal("0")
    assert result.unmatched_external_amount == Decimal("100")
    assert result.status is ReconciliationStatus.UNRECONCILED


def test_empty_external_set() -> None:
    result = _service().reconcile(
        [_item("I1", "100", ReconciliationSide.INTERNAL)],
        [],
    )

    assert result.unmatched_internal_amount == Decimal("100")
    assert result.status is ReconciliationStatus.UNRECONCILED


def test_zero_amount_handling() -> None:
    result = _service().reconcile(
        [_item("I1", "0", ReconciliationSide.INTERNAL)],
        [_item("E1", "0", ReconciliationSide.EXTERNAL)],
    )

    assert result.status is ReconciliationStatus.FULLY_RECONCILED
    assert result.matched_amount == Decimal("0")
    assert result.allocation_count == 0


def test_explanation_generation() -> None:
    result = _service().reconcile(
        [_item("I1", "100", ReconciliationSide.INTERNAL)],
        [_item("E1", "100", ReconciliationSide.EXTERNAL)],
    )

    assert "100 matched across 1 internal obligations and 1 external settlements" in result.explanation
    assert "capacity constraints satisfied" in result.explanation


def test_match_rate_calculation() -> None:
    result = _service().reconcile(
        [_item("I1", "100", ReconciliationSide.INTERNAL)],
        [_item("E1", "40", ReconciliationSide.EXTERNAL)],
    )

    assert result.match_rate == Decimal("0.4")


def test_reconciliation_result_adapts_to_residual_observation() -> None:
    result = _service().reconcile(
        [_item("I1", "100", ReconciliationSide.INTERNAL)],
        [_item("E1", "70", ReconciliationSide.EXTERNAL)],
    )
    residual = _service().to_residual_observation(
        result,
        residual_id="recon-residual",
        control_id="reconciliation",
        domain="SETTLEMENT",
        timestamp=PERIOD_START,
    )

    assert residual.expected_amount == Decimal("30")
    assert residual.actual_amount == Decimal("0")
    assert residual.residual_amount == Decimal("-30")
    assert residual.metadata["reconciliation_id"] == result.reconciliation_id


def _service() -> ReconciliationService:
    return ReconciliationService()


def _item(
    item_id: str,
    amount: str,
    side: ReconciliationSide,
    *,
    currency: str = "INR",
    timestamp: datetime = PERIOD_START,
    entity_id: str | None = "entity-a",
    account_id: str | None = "account-a",
    merchant_id: str | None = "merchant-a",
    partner_id: str | None = "partner-a",
    reference_id: str | None = None,
) -> ReconciliationItem:
    return ReconciliationItem(
        item_id=item_id,
        side=side,
        item_type=(
            ReconciliationItemType.SETTLEMENT_OBLIGATION
            if side is ReconciliationSide.INTERNAL
            else ReconciliationItemType.BANK_SETTLEMENT
        ),
        entity_id=entity_id,
        account_id=account_id,
        merchant_id=merchant_id,
        partner_id=partner_id,
        amount=Decimal(amount),
        currency=currency,
        timestamp=timestamp,
        reference_id=reference_id,
    )


def _allocation(amount: str) -> MatchAllocation:
    return MatchAllocation(
        allocation_id="A1",
        internal_item_id="I1",
        external_item_id="E1",
        allocated_amount=Decimal(amount),
        currency="INR",
        confidence=Decimal("1"),
        reason="test",
        constraints_satisfied=True,
    )