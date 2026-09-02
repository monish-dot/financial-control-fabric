"""Deterministic synthetic residual populations for Phase 3."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.anomaly.residual_models import ResidualObservation
from backend.controls.models import ControlDomain, ControlStatus


PERIOD_START = datetime(2026, 2, 1, tzinfo=timezone.utc)


def build_residual_populations() -> dict[str, list[ResidualObservation]]:
    """Return stable, drifting, shifted, timing-like, and domain populations."""

    populations = {
        "stable": ["0", "0", "0", "1", "-1", "0", "0", "0"],
        "increasing_variance": ["0", "1", "-1", "3", "-5", "8", "-13", "21"],
        "persistent_positive_bias": ["10", "11", "9", "12", "10", "11", "13", "12"],
        "distribution_shift_baseline": ["0", "0", "0", "1", "-1", "0", "1"],
        "distribution_shift_current": ["25", "30", "20", "35", "28", "32", "27"],
        "timing_like": ["0", "0.5", "0.5", "0.5", "0.5", "0", "0", "0"],
        "domain_nodal_escrow": ["0", "0", "1", "-1"],
        "domain_settlement": ["0", "0.25", "-0.25", "0"],
        "domain_merchant_payout": ["0", "2", "0", "-2"],
        "domain_revenue_recognition": ["0", "0", "1", "0"],
        "domain_cross_entity": ["0", "-1", "0", "1"],
    }
    domains = {
        "domain_nodal_escrow": ControlDomain.NODAL_ESCROW,
        "domain_settlement": ControlDomain.SETTLEMENT,
        "domain_merchant_payout": ControlDomain.MERCHANT_PAYOUT,
        "domain_revenue_recognition": ControlDomain.REVENUE_RECOGNITION,
        "domain_cross_entity": ControlDomain.CROSS_ENTITY,
    }
    return {
        name: _population(
            name,
            amounts,
            domain=domains.get(name, ControlDomain.NODAL_ESCROW),
        )
        for name, amounts in populations.items()
    }


def _population(
    name: str,
    amounts: list[str],
    *,
    domain: ControlDomain,
) -> list[ResidualObservation]:
    start = PERIOD_START
    observations: list[ResidualObservation] = []
    for index, amount_text in enumerate(amounts):
        amount = Decimal(amount_text)
        observations.append(
            ResidualObservation(
                residual_id=f"{name}_{index + 1:03d}",
                control_id=f"{domain.value.lower()}_synthetic",
                domain=domain,
                entity_id="synthetic-entity",
                account_id="synthetic-account",
                merchant_id="synthetic-merchant",
                partner_id="synthetic-partner",
                timestamp=start + timedelta(days=index),
                expected_amount=Decimal("0"),
                actual_amount=amount,
                residual_amount=amount,
                currency="INR",
                status=ControlStatus.PASS if amount == 0 else ControlStatus.FAIL,
                metadata={"synthetic": True, "population": name},
            )
        )
    return observations