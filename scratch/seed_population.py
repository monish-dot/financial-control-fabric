"""
Deterministic Population Seeder for Financial Control Fabric.
Seeds at least 1,000 canonical financial events and residual populations
into data/financial_control.db using existing backend models and repositories.
Does NOT modify any backend source code.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid

from backend.database.connection import Database
from backend.repositories.financial_event import FinancialEventRepository
from backend.anomaly.residual_store import ResidualStore
from backend.models.financial_event import FinancialEvent, EventType
from backend.anomaly.residual_models import ResidualObservation
from backend.controls.models import ControlDomain, ControlStatus
from data.residual_scenarios import build_residual_populations


def seed():
    db = Database()
    db.initialize()
    event_repo = FinancialEventRepository(db.session_factory)
    residual_store = ResidualStore(db.session_factory)

    base_time = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    events_to_create = []

    print("Generating 1,000+ deterministic events...")

    # 1. Normal Merchant Payouts: 400 events (200 pairs of payment + payout + fees)
    merchants = ["merchant-alpha", "merchant-beta", "merchant-gamma", "merchant-delta", "merchant-omega"]
    for i in range(1, 134):
        m = merchants[i % len(merchants)]
        t = base_time + timedelta(minutes=i * 10)
        amt = Decimal(f"{(1000 + (i * 37) % 5000):.2f}")
        fee = Decimal(f"{(amt * Decimal('0.02')):.2f}")
        net_payout = amt - fee

        # Payment event
        events_to_create.append(FinancialEvent(
            event_id=f"evt-pay-{i:04d}",
            event_type=EventType.PAYMENT,
            source_system="gateway",
            source_id=f"gw_pay_{i:04d}",
            entity_id="entity-corp",
            account_id="acct-main",
            merchant_id=m,
            partner_id="partner-hdfc",
            amount=amt,
            currency="INR",
            event_timestamp=t,
            effective_timestamp=t,
            status="posted",
            metadata={"channel": "UPI", "batch": "batch-1"}
        ))
        # Fee event
        events_to_create.append(FinancialEvent(
            event_id=f"evt-fee-{i:04d}",
            event_type=EventType.FEE,
            source_system="billing",
            source_id=f"bill_fee_{i:04d}",
            entity_id="entity-corp",
            account_id="acct-main",
            merchant_id=m,
            partner_id="partner-hdfc",
            amount=fee,
            currency="INR",
            event_timestamp=t,
            effective_timestamp=t,
            status="posted",
            metadata={"type": "mdr"}
        ))
        # Payout event
        events_to_create.append(FinancialEvent(
            event_id=f"evt-out-{i:04d}",
            event_type=EventType.PAYOUT,
            source_system="banking_rail",
            source_id=f"bank_out_{i:04d}",
            entity_id="entity-corp",
            account_id="acct-main",
            merchant_id=m,
            partner_id="partner-hdfc",
            amount=net_payout,
            currency="INR",
            event_timestamp=t + timedelta(minutes=5),
            effective_timestamp=t + timedelta(minutes=5),
            status="settled",
            metadata={"utr": f"UTR{i:06d}"}
        ))

    # 2. Nodal Escrow Events: 250 events
    for i in range(1, 251):
        t = base_time + timedelta(minutes=i * 5)
        etype = EventType.PAYMENT if i % 2 == 0 else EventType.BANK_CREDIT
        events_to_create.append(FinancialEvent(
            event_id=f"evt-nodal-{i:04d}",
            event_type=etype,
            source_system="nodal_gateway",
            source_id=f"nodal_{i:04d}",
            entity_id="entity-corp",
            account_id="nodal-escrow-01",
            merchant_id="merchant-alpha",
            partner_id="partner-icici",
            amount=Decimal(f"{(500 + (i * 19) % 2000):.2f}"),
            currency="INR",
            event_timestamp=t,
            effective_timestamp=t,
            status="posted",
            metadata={"account": "nodal-escrow-01"}
        ))

    # 3. Settlement Events: 200 events
    for i in range(1, 201):
        t = base_time + timedelta(minutes=i * 8)
        partner = "partner-hdfc" if i % 2 == 0 else "partner-sbi"
        etype = EventType.SETTLEMENT if i % 2 == 0 else EventType.BANK_CREDIT
        events_to_create.append(FinancialEvent(
            event_id=f"evt-settle-{i:04d}",
            event_type=etype,
            source_system="clearing",
            source_id=f"clear_{i:04d}",
            entity_id="entity-corp",
            account_id="settle-acct",
            partner_id=partner,
            amount=Decimal(f"{(10000 + (i * 53) % 10000):.2f}"),
            currency="INR",
            event_timestamp=t,
            effective_timestamp=t,
            status="posted",
            metadata={"cycle": "T+1"}
        ))

    # 4. Revenue Recognition: 100 events
    for i in range(1, 101):
        t = base_time + timedelta(hours=i)
        events_to_create.append(FinancialEvent(
            event_id=f"evt-rev-{i:04d}",
            event_type=EventType.REVENUE_RECOGNITION,
            source_system="erp_ledger",
            source_id=f"erp_{i:04d}",
            entity_id="entity-corp",
            account_id="rev-acct",
            amount=Decimal(f"{(2500 + (i * 41) % 5000):.2f}"),
            currency="INR",
            event_timestamp=t,
            effective_timestamp=t,
            status="posted",
            metadata={"standard": "ASC-606"}
        ))

    # 5. Cross Entity Transfers: 100 events
    for i in range(1, 101):
        t = base_time + timedelta(hours=i * 2)
        events_to_create.append(FinancialEvent(
            event_id=f"evt-xent-{i:04d}",
            event_type=EventType.INTERCOMPANY_TRANSFER,
            source_system="treasury",
            source_id=f"trsy_{i:04d}",
            entity_id="entity-corp",
            account_id="intercompany-main",
            amount=Decimal(f"{(50000 + (i * 97) % 50000):.2f}"),
            currency="INR",
            event_timestamp=t,
            effective_timestamp=t,
            status="posted",
            metadata={"dest_entity": "entity-subsidiary-1"}
        ))

    # 6. Controlled Exceptions for Demonstration:
    # A) Missing Event: Payment of 10,000 INR to merchant-missing with NO payout
    events_to_create.append(FinancialEvent(
        event_id="demo-missing-payment-10000",
        event_type=EventType.PAYMENT,
        source_system="gateway",
        source_id="gw_missing_demo_01",
        entity_id="entity-corp",
        account_id="acct-main",
        merchant_id="merchant-missing",
        partner_id="partner-hdfc",
        amount=Decimal("10000.00"),
        currency="INR",
        event_timestamp=base_time + timedelta(days=2),
        effective_timestamp=base_time + timedelta(days=2),
        status="posted",
        metadata={"channel": "UPI", "scenario": "missing_payout"}
    ))

    # B) Duplicate Event: Two identical payouts of 5,000 INR
    events_to_create.append(FinancialEvent(
        event_id="demo-duplicate-payout-01",
        event_type=EventType.PAYOUT,
        source_system="banking_rail",
        source_id="dup_payout_ref_01",
        entity_id="entity-corp",
        account_id="acct-main",
        merchant_id="merchant-dup",
        amount=Decimal("5000.00"),
        currency="INR",
        event_timestamp=base_time + timedelta(days=2, hours=1),
        effective_timestamp=base_time + timedelta(days=2, hours=1),
        status="settled",
        metadata={"scenario": "duplicate_payout"}
    ))
    events_to_create.append(FinancialEvent(
        event_id="demo-duplicate-payout-02",
        event_type=EventType.PAYOUT,
        source_system="banking_rail",
        source_id="dup_payout_ref_01", # Same source id!
        entity_id="entity-corp",
        account_id="acct-main",
        merchant_id="merchant-dup",
        amount=Decimal("5000.00"),
        currency="INR",
        event_timestamp=base_time + timedelta(days=2, hours=1, minutes=1),
        effective_timestamp=base_time + timedelta(days=2, hours=1, minutes=1),
        status="settled",
        metadata={"scenario": "duplicate_payout"}
    ))

    # C) Fee Difference: Payment with unexpected fee mismatch
    events_to_create.append(FinancialEvent(
        event_id="demo-fee-diff-payment",
        event_type=EventType.PAYMENT,
        source_system="gateway",
        source_id="gw_fee_diff_01",
        entity_id="entity-corp",
        account_id="acct-main",
        merchant_id="merchant-fee-skew",
        amount=Decimal("8000.00"),
        currency="INR",
        event_timestamp=base_time + timedelta(days=2, hours=3),
        effective_timestamp=base_time + timedelta(days=2, hours=3),
        status="posted",
        metadata={"scenario": "fee_difference"}
    ))
    events_to_create.append(FinancialEvent(
        event_id="demo-fee-diff-fee",
        event_type=EventType.FEE,
        source_system="billing",
        source_id="bill_fee_skew_01",
        entity_id="entity-corp",
        account_id="acct-main",
        merchant_id="merchant-fee-skew",
        amount=Decimal("450.00"), # Skewed fee
        currency="INR",
        event_timestamp=base_time + timedelta(days=2, hours=3),
        effective_timestamp=base_time + timedelta(days=2, hours=3),
        status="posted",
        metadata={"scenario": "fee_difference"}
    ))

    print(f"Persisting {len(events_to_create)} financial events...")
    inserted_count = 0
    for ev in events_to_create:
        res = event_repo.create_event(ev)
        if res.created:
            inserted_count += 1

    print(f"Inserted {inserted_count} new events (total evaluated: {len(events_to_create)}).")

    # 7. Seed Residual Observations across domains using build_residual_populations()
    print("Seeding residual observations for distribution intelligence...")
    populations = build_residual_populations()
    seeded_residuals = 0
    for pop_name, obs_list in populations.items():
        for obs in obs_list:
            try:
                residual_store.record_residual(obs)
                seeded_residuals += 1
            except Exception:
                pass

    # Add specific controlled exception observations
    extra_exceptions = [
        ResidualObservation(
            residual_id="res-crit-missing-001",
            control_id="merchant_payout_entitlement",
            domain=ControlDomain.MERCHANT_PAYOUT,
            entity_id="entity-corp",
            account_id="acct-main",
            merchant_id="merchant-missing",
            timestamp=base_time + timedelta(days=2),
            expected_amount=Decimal("10000.00"),
            actual_amount=Decimal("0.00"),
            residual_amount=Decimal("-10000.00"),
            currency="INR",
            status=ControlStatus.FAIL,
            metadata={"root_cause_hint": "MISSING_EVENT", "severity": "CRITICAL"}
        ),
        ResidualObservation(
            residual_id="res-crit-dup-002",
            control_id="merchant_payout_entitlement",
            domain=ControlDomain.MERCHANT_PAYOUT,
            entity_id="entity-corp",
            account_id="acct-main",
            merchant_id="merchant-dup",
            timestamp=base_time + timedelta(days=2, hours=1),
            expected_amount=Decimal("5000.00"),
            actual_amount=Decimal("10000.00"),
            residual_amount=Decimal("5000.00"),
            currency="INR",
            status=ControlStatus.FAIL,
            metadata={"root_cause_hint": "DUPLICATE_EVENT", "severity": "CRITICAL"}
        ),
        ResidualObservation(
            residual_id="res-watch-fee-003",
            control_id="merchant_payout_entitlement",
            domain=ControlDomain.MERCHANT_PAYOUT,
            entity_id="entity-corp",
            account_id="acct-main",
            merchant_id="merchant-fee-skew",
            timestamp=base_time + timedelta(days=2, hours=3),
            expected_amount=Decimal("7840.00"),
            actual_amount=Decimal("7550.00"),
            residual_amount=Decimal("-290.00"),
            currency="INR",
            status=ControlStatus.FAIL,
            metadata={"root_cause_hint": "FEE_DIFFERENCE", "severity": "WATCH"}
        ),
        ResidualObservation(
            residual_id="res-anom-settle-004",
            control_id="multi_bank_partner_settlement",
            domain=ControlDomain.SETTLEMENT,
            entity_id="entity-corp",
            partner_id="partner-sbi",
            timestamp=base_time + timedelta(days=1),
            expected_amount=Decimal("50000.00"),
            actual_amount=Decimal("48500.00"),
            residual_amount=Decimal("-1500.00"),
            currency="INR",
            status=ControlStatus.FAIL,
            metadata={"root_cause_hint": "TIMING_DIFFERENCE", "severity": "ANOMALOUS"}
        )
    ]
    for r in extra_exceptions:
        try:
            residual_store.record_residual(r)
            seeded_residuals += 1
        except Exception:
            pass

    print(f"Seeded {seeded_residuals} residual observations.")
    total_events = len(event_repo.list_events(limit=2000))
    total_res = len(residual_store.list_residuals(limit=2000))
    print(f"Database ready: {total_events} events, {total_res} residuals.")
    db.dispose()


if __name__ == "__main__":
    seed()
