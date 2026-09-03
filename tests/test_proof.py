"""Comprehensive tests for Phase 6: Tamper-Evident Cryptographic Control Proof."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest
from fastapi.testclient import TestClient

from backend.agent.investigator import FinanceController
from backend.agent.models import AgentState, ControlDomain, InvestigationRequest
from backend.anomaly.engine import ResidualIntelligenceEngine
from backend.anomaly.residual_models import ResidualObservation
from backend.api.main import create_app
from backend.controls.merchant_payout import MerchantPayoutControl
from backend.controls.models import (
    ControlResult,
    ControlStatus,
    MerchantPayoutContext,
)
from backend.database.connection import Database
from backend.models.financial_event import EventType, FinancialEvent
from backend.proof.generator import ControlProofGenerator
from backend.proof.hashing import (
    EMPTY_TREE_ROOT,
    canonical_event_bytes,
    canonical_event_hash,
    canonical_sort_events,
    hash_pair,
)
from backend.proof.merkle import MerkleTree, verify_membership
from backend.proof.models import (
    ControlProof,
    MerkleProofStep,
    VerificationFailureReason,
)
from backend.proof.repository import ControlProofRepository
from backend.proof.service import ControlProofService
from backend.proof.verifier import ControlProofVerifier
from backend.repositories.financial_event import FinancialEventRepository

START = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)


def _make_event(
    event_id: str,
    event_type: EventType = EventType.PAYMENT,
    amount: str = "100.00",
    offset_minutes: int = 0,
    merchant_id: str | None = "merchant-1",
    metadata: dict | None = None,
) -> FinancialEvent:
    ts = START + timedelta(minutes=offset_minutes)
    return FinancialEvent(
        event_id=event_id,
        event_type=event_type,
        source_system="synthetic",
        source_id=f"src_{event_id}",
        entity_id="entity-1",
        account_id="account-1",
        merchant_id=merchant_id,
        partner_id="partner-1",
        amount=Decimal(amount),
        currency="INR",
        event_timestamp=ts,
        effective_timestamp=ts,
        status="posted",
        metadata=metadata or {},
    )


@pytest.fixture
def proof_env(tmp_path):
    database = Database(tmp_path / "test_proof.db")
    database.initialize()
    event_repo = FinancialEventRepository(database.session_factory)
    proof_repo = ControlProofRepository(database.session_factory)
    service = ControlProofService(proof_repo, event_repo)
    controller = FinanceController(event_repo, proof_service=service)
    yield {
        "database": database,
        "event_repo": event_repo,
        "proof_repo": proof_repo,
        "service": service,
        "controller": controller,
    }
    database.dispose()


@pytest.fixture
def client(tmp_path):
    database = Database(tmp_path / "test_api_proof.db")
    database.initialize()
    with TestClient(create_app(database)) as test_client:
        yield test_client
    database.dispose()


# ==============================================================================
# A. Canonical Serialization & Canonical Ordering
# ==============================================================================


def test_canonical_serialization_determinism() -> None:
    event = _make_event("evt-1", amount="250.75", metadata={"b": 2, "a": 1})
    bytes_1 = canonical_event_bytes(event)
    bytes_2 = canonical_event_bytes(event)

    assert bytes_1 == bytes_2
    parsed = json.loads(bytes_1.decode("utf-8"))
    assert list(parsed["metadata"].keys()) == ["a", "b"]
    assert parsed["amount"] == "250.75"


def test_canonical_serialization_decimal_exactness() -> None:
    event1 = _make_event("evt-1", amount="100.50")
    event2 = _make_event("evt-2", amount="100.500")

    parsed1 = json.loads(canonical_event_bytes(event1).decode("utf-8"))
    parsed2 = json.loads(canonical_event_bytes(event2).decode("utf-8"))

    assert parsed1["amount"] == "100.50"
    assert parsed2["amount"] == "100.500"
    assert canonical_event_hash(event1) != canonical_event_hash(event2)


def test_canonical_serialization_metadata_key_ordering() -> None:
    event1 = _make_event("evt-1", metadata={"z": 1, "a": 2, "m": 3})
    event2 = _make_event("evt-1", metadata={"a": 2, "m": 3, "z": 1})

    assert canonical_event_bytes(event1) == canonical_event_bytes(event2)
    assert canonical_event_hash(event1) == canonical_event_hash(event2)


def test_canonical_serialization_timestamp_utc_consistency() -> None:
    # Aware UTC vs Naive (which is treated as UTC)
    ts_aware = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
    ts_naive = datetime(2026, 4, 1, 10, 0)

    event_aware = _make_event("evt-1")
    event_aware.event_timestamp = ts_aware
    event_aware.effective_timestamp = ts_aware

    event_naive = _make_event("evt-1")
    event_naive.event_timestamp = ts_naive
    event_naive.effective_timestamp = ts_naive

    assert canonical_event_bytes(event_aware) == canonical_event_bytes(event_naive)
    assert canonical_event_hash(event_aware) == canonical_event_hash(event_naive)


def test_canonical_ordering_different_input_permutations_produce_same_root() -> None:
    """Correction 1: Permuted input event lists produce the identical Merkle root."""
    e1 = _make_event("evt-1", offset_minutes=10)
    e2 = _make_event("evt-2", offset_minutes=20)
    e3 = _make_event("evt-3", offset_minutes=30)

    perm1 = [e1, e2, e3]
    perm2 = [e3, e1, e2]
    perm3 = [e2, e3, e1]

    root1 = MerkleTree.from_events(perm1).root
    root2 = MerkleTree.from_events(perm2).root
    root3 = MerkleTree.from_events(perm3).root

    assert root1 == root2 == root3
    assert len(root1) == 64


# ==============================================================================
# B. SHA-256 Hashing
# ==============================================================================


def test_sha256_leaf_hash_determinism_and_format() -> None:
    event = _make_event("evt-1", amount="1500.00")
    h = canonical_event_hash(event)

    assert len(h) == 64
    assert h == h.lower()
    assert all(c in "0123456789abcdef" for c in h)
    assert h == canonical_event_hash(event)


def test_sha256_leaf_hash_tamper_sensitivity() -> None:
    original = _make_event("evt-1", amount="100.00")
    base_hash = canonical_event_hash(original)

    # Change amount by 1 cent
    tampered_amount = _make_event("evt-1", amount="100.01")
    assert canonical_event_hash(tampered_amount) != base_hash

    # Change currency
    tampered_currency = _make_event("evt-1")
    tampered_currency.currency = "USD"
    assert canonical_event_hash(tampered_currency) != base_hash

    # Change event_type
    tampered_type = _make_event("evt-1", event_type=EventType.REFUND)
    assert canonical_event_hash(tampered_type) != base_hash

    # Change timestamp
    tampered_ts = _make_event("evt-1", offset_minutes=1)
    assert canonical_event_hash(tampered_ts) != base_hash


# ==============================================================================
# C. Merkle Tree & Odd-Leaf Duplication Rule
# ==============================================================================


def test_merkle_tree_empty_set() -> None:
    tree = MerkleTree([])
    assert tree.root == EMPTY_TREE_ROOT


def test_merkle_tree_single_event() -> None:
    e1 = _make_event("evt-1")
    h1 = canonical_event_hash(e1)
    tree = MerkleTree([h1])
    assert tree.root == h1


def test_merkle_tree_even_leaves() -> None:
    e1 = _make_event("evt-1", offset_minutes=1)
    e2 = _make_event("evt-2", offset_minutes=2)
    h1 = canonical_event_hash(e1)
    h2 = canonical_event_hash(e2)

    tree = MerkleTree([h1, h2])
    expected_root = hash_pair(h1, h2)
    assert tree.root == expected_root


def test_merkle_tree_odd_leaves_duplicate_rule() -> None:
    """Documented odd-leaf rule: duplicate final hash before computing next level."""
    e1 = _make_event("evt-1", offset_minutes=1)
    e2 = _make_event("evt-2", offset_minutes=2)
    e3 = _make_event("evt-3", offset_minutes=3)

    h1 = canonical_event_hash(e1)
    h2 = canonical_event_hash(e2)
    h3 = canonical_event_hash(e3)

    # 3 leaves -> level 0: [h1, h2, h3, h3]
    # level 1: [hash_pair(h1, h2), hash_pair(h3, h3)]
    # level 2 (root): hash_pair(level1[0], level1[1])
    p1 = hash_pair(h1, h2)
    p2 = hash_pair(h3, h3)
    expected_root = hash_pair(p1, p2)

    tree = MerkleTree([h1, h2, h3])
    assert tree.root == expected_root


def test_merkle_tree_five_leaves() -> None:
    events = [_make_event(f"evt-{i}", offset_minutes=i) for i in range(5)]
    leaves = [canonical_event_hash(e) for e in events]
    tree = MerkleTree(leaves)

    # Level 0 (5 leaves -> duplicate 5th -> 6):
    # p0 = hash(0, 1), p1 = hash(2, 3), p2 = hash(4, 4)
    # Level 1 (3 nodes -> duplicate 3rd -> 4):
    # g0 = hash(p0, p1), g1 = hash(p2, p2)
    # Level 2 (2 nodes):
    # root = hash(g0, g1)
    p0 = hash_pair(leaves[0], leaves[1])
    p1 = hash_pair(leaves[2], leaves[3])
    p2 = hash_pair(leaves[4], leaves[4])
    g0 = hash_pair(p0, p1)
    g1 = hash_pair(p2, p2)
    expected_root = hash_pair(g0, g1)

    assert tree.root == expected_root


# ==============================================================================
# D. Proof Generation & Persistence
# ==============================================================================


def test_proof_generation_and_persistence(proof_env) -> None:
    service: ControlProofService = proof_env["service"]
    proof_repo: ControlProofRepository = proof_env["proof_repo"]

    events = [
        _make_event("p1", EventType.PAYMENT, "1000.00", offset_minutes=1),
        _make_event("f1", EventType.FEE, "50.00", offset_minutes=2),
    ]
    context = MerchantPayoutContext(
        merchant_id="merchant-1",
        period_start=START,
        period_end=START + timedelta(hours=1),
        currency="INR",
        tolerance=Decimal("0.00"),
    )
    control = MerchantPayoutControl()
    result = control.evaluate(events, context)

    proof = service.generate_proof(result, context, events, proof_id="proof-001")

    assert proof.proof_id == "proof-001"
    assert proof.domain is ControlDomain.MERCHANT_PAYOUT
    assert proof.event_count == 2
    assert proof.event_ids == ["p1", "f1"]
    assert proof.expected_amount == Decimal("950.00")
    assert proof.actual_amount == Decimal("0.00")
    assert proof.residual_amount == Decimal("-950.00")
    assert proof.currency == "INR"
    assert proof.control_status is ControlStatus.FAIL
    assert len(proof.merkle_root) == 64

    # Verify database persistence round-trip
    retrieved = proof_repo.get_proof("proof-001")
    assert retrieved is not None
    assert retrieved.model_dump() == proof.model_dump()
    assert isinstance(retrieved.expected_amount, Decimal)


# ==============================================================================
# E. Proof Verification & Failure Mode Distinctions
# ==============================================================================


def test_proof_verification_valid(proof_env) -> None:
    service: ControlProofService = proof_env["service"]
    events = [
        _make_event("p1", EventType.PAYMENT, "1000.00", offset_minutes=1),
        _make_event("f1", EventType.FEE, "50.00", offset_minutes=2),
    ]
    context = MerchantPayoutContext(
        merchant_id="merchant-1",
        period_start=START,
        period_end=START + timedelta(hours=1),
        currency="INR",
        tolerance=Decimal("0.00"),
    )
    control = MerchantPayoutControl()
    result = control.evaluate(events, context)
    proof = service.generate_proof(result, context, events, proof_id="proof-valid")

    verification = service.verify_proof("proof-valid", events)

    assert verification.valid is True
    assert verification.tampering_detected is False
    assert verification.control_result_consistent is True
    assert verification.failure_reason is VerificationFailureReason.VALID
    assert verification.merkle_root_computed == proof.merkle_root


def test_proof_verification_detects_event_tampering(proof_env) -> None:
    service: ControlProofService = proof_env["service"]
    events = [
        _make_event("p1", EventType.PAYMENT, "1000.00", offset_minutes=1),
        _make_event("f1", EventType.FEE, "50.00", offset_minutes=2),
    ]
    context = MerchantPayoutContext(
        merchant_id="merchant-1",
        period_start=START,
        period_end=START + timedelta(hours=1),
        currency="INR",
        tolerance=Decimal("0.00"),
    )
    control = MerchantPayoutControl()
    result = control.evaluate(events, context)
    service.generate_proof(result, context, events, proof_id="proof-tamper")

    # Tamper with the amount of event p1
    tampered_events = [
        _make_event("p1", EventType.PAYMENT, "1000.01", offset_minutes=1),
        events[1],
    ]
    verification = service.verify_proof("proof-tamper", tampered_events)

    assert verification.valid is False
    assert verification.tampering_detected is True
    assert verification.failure_reason is VerificationFailureReason.EVENT_TAMPERED
    assert "event content was altered" in verification.metadata["detail"]


def test_proof_verification_detects_missing_event(proof_env) -> None:
    service: ControlProofService = proof_env["service"]
    events = [
        _make_event("p1", EventType.PAYMENT, "1000.00", offset_minutes=1),
        _make_event("f1", EventType.FEE, "50.00", offset_minutes=2),
    ]
    context = MerchantPayoutContext(
        merchant_id="merchant-1",
        period_start=START,
        period_end=START + timedelta(hours=1),
        currency="INR",
    )
    result = MerchantPayoutControl().evaluate(events, context)
    service.generate_proof(result, context, events, proof_id="proof-missing")

    # Missing f1
    verification = service.verify_proof("proof-missing", [events[0]])

    assert verification.valid is False
    assert verification.tampering_detected is True
    assert verification.failure_reason is VerificationFailureReason.EVENT_MISSING
    assert "f1" in verification.metadata["detail"]


def test_proof_verification_detects_added_event(proof_env) -> None:
    service: ControlProofService = proof_env["service"]
    events = [_make_event("p1", EventType.PAYMENT, "1000.00")]
    context = MerchantPayoutContext(
        merchant_id="merchant-1",
        period_start=START,
        period_end=START + timedelta(hours=1),
        currency="INR",
    )
    result = MerchantPayoutControl().evaluate(events, context)
    service.generate_proof(result, context, events, proof_id="proof-added")

    # Extra event added
    augmented = [events[0], _make_event("extra-event", EventType.ADJUSTMENT, "10.00")]
    verification = service.verify_proof("proof-added", augmented)

    assert verification.valid is False
    assert verification.tampering_detected is True
    assert verification.failure_reason is VerificationFailureReason.EVENT_ADDED
    assert "extra-event" in verification.metadata["detail"]


def test_proof_verification_detects_control_result_mismatch(proof_env) -> None:
    """Correction 2: Verifier re-evaluates through Financial Control Kernel."""
    proof_repo: ControlProofRepository = proof_env["proof_repo"]
    verifier = ControlProofVerifier()

    events = [_make_event("p1", EventType.PAYMENT, "1000.00")]
    context = MerchantPayoutContext(
        merchant_id="merchant-1",
        period_start=START,
        period_end=START + timedelta(hours=1),
        currency="INR",
    )
    result = MerchantPayoutControl().evaluate(events, context)
    proof = ControlProofGenerator().generate(result, context, events, proof_id="proof-mismatch")

    # Forge the expected_amount in the proof record (e.g. attacker tampered with DB record)
    forged_proof = proof.model_copy(
        update={
            "expected_amount": Decimal("1500.00"),
            "residual_amount": proof.actual_amount - Decimal("1500.00"),
        }
    )
    proof_repo.create_proof(forged_proof)

    # Verification will re-run the kernel, get expected=1000.00 != proof expected=1500.00
    verification = verifier.verify(forged_proof, events)

    assert verification.valid is False
    assert verification.control_result_consistent is False
    assert verification.failure_reason is VerificationFailureReason.CONTROL_RESULT_MISMATCH
    assert "Re-evaluated control result differs from proof" in verification.metadata["detail"]


# ==============================================================================
# F. Merkle Membership Proofs
# ==============================================================================


def test_membership_proof_valid_odd_and_even_trees() -> None:
    events = [_make_event(f"evt-{i}", offset_minutes=i) for i in range(5)]
    tree = MerkleTree.from_events(events)

    # Test membership for each event in the 5-leaf tree
    for idx, event in enumerate(events):
        leaf_hash = canonical_event_hash(event)
        steps = tree.generate_membership_proof(idx)
        assert verify_membership(leaf_hash, steps, tree.root) is True


def test_membership_proof_invalid_event_hash() -> None:
    events = [_make_event(f"evt-{i}", offset_minutes=i) for i in range(4)]
    tree = MerkleTree.from_events(events)
    steps = tree.generate_membership_proof(0)

    fake_leaf = canonical_event_hash(_make_event("fake-event"))
    assert verify_membership(fake_leaf, steps, tree.root) is False


def test_membership_proof_invalid_sibling_hash() -> None:
    events = [_make_event(f"evt-{i}", offset_minutes=i) for i in range(4)]
    tree = MerkleTree.from_events(events)
    steps = tree.generate_membership_proof(0)

    # Corrupt a sibling step
    corrupted_steps = [
        MerkleProofStep(sibling_hash="0" * 64, position=steps[0].position),
        *steps[1:],
    ]
    leaf_hash = canonical_event_hash(events[0])
    assert verify_membership(leaf_hash, corrupted_steps, tree.root) is False


def test_membership_proof_invalid_root() -> None:
    events = [_make_event(f"evt-{i}", offset_minutes=i) for i in range(4)]
    tree = MerkleTree.from_events(events)
    steps = tree.generate_membership_proof(0)
    leaf_hash = canonical_event_hash(events[0])

    assert verify_membership(leaf_hash, steps, "f" * 64) is False


def test_membership_proof_nonexistent_event(proof_env) -> None:
    service: ControlProofService = proof_env["service"]
    events = [_make_event("evt-1")]
    context = MerchantPayoutContext(
        merchant_id="merchant-1",
        period_start=START,
        period_end=START + timedelta(hours=1),
        currency="INR",
    )
    result = MerchantPayoutControl().evaluate(events, context)
    service.generate_proof(result, context, events, proof_id="proof-mem")

    with pytest.raises(ValueError, match="not present in proof"):
        service.get_membership_proof("proof-mem", "nonexistent-event", events)


# ==============================================================================
# G. API Lifecycle & Verification Endpoints
# ==============================================================================


def test_api_proof_lifecycle(client: TestClient) -> None:
    # 1. Ingest test events
    event1 = _make_event("api-p1", EventType.PAYMENT, "5000.00", offset_minutes=1)
    event2 = _make_event("api-f1", EventType.FEE, "100.00", offset_minutes=2)
    client.post("/events", json=event1.model_dump(mode="json"))
    client.post("/events", json=event2.model_dump(mode="json"))

    context = MerchantPayoutContext(
        merchant_id="merchant-1",
        period_start=START,
        period_end=START + timedelta(hours=1),
        currency="INR",
    )
    eval_resp = client.post(
        "/controls/evaluate/MERCHANT_PAYOUT",
        json={"events": [event1.model_dump(mode="json"), event2.model_dump(mode="json")], "context": context.model_dump(mode="json")},
    )
    assert eval_resp.status_code == 200
    control_result = eval_resp.json()

    # 2. Generate Proof via API
    gen_resp = client.post(
        "/proofs/generate",
        json={
            "control_result": control_result,
            "context": context.model_dump(mode="json"),
            "events": [event1.model_dump(mode="json"), event2.model_dump(mode="json")],
            "proof_id": "api-proof-1",
        },
    )
    assert gen_resp.status_code == 201
    proof = gen_resp.json()
    assert proof["proof_id"] == "api-proof-1"
    assert proof["event_count"] == 2
    assert len(proof["merkle_root"]) == 64

    # 3. Retrieve Proof via API
    get_resp = client.get("/proofs/api-proof-1")
    assert get_resp.status_code == 200
    assert get_resp.json()["merkle_root"] == proof["merkle_root"]

    # 4. Verify Proof via API
    verify_resp = client.post(
        "/proofs/api-proof-1/verify",
        json={"events": [event1.model_dump(mode="json"), event2.model_dump(mode="json")]},
    )
    assert verify_resp.status_code == 200
    v_body = verify_resp.json()
    assert v_body["valid"] is True
    assert v_body["failure_reason"] == "VALID"
    assert v_body["tampering_detected"] is False

    # 5. Merkle Membership via API
    mem_resp = client.get("/proofs/api-proof-1/events/api-p1/membership")
    assert mem_resp.status_code == 200
    m_body = mem_resp.json()
    assert m_body["verified"] is True
    assert m_body["event_id"] == "api-p1"
    assert len(m_body["proof_steps"]) == 1


def test_api_proof_verification_detects_tamper(client: TestClient) -> None:
    event = _make_event("api-single", EventType.PAYMENT, "100.00")
    context = MerchantPayoutContext(
        merchant_id="merchant-1",
        period_start=START,
        period_end=START + timedelta(hours=1),
        currency="INR",
    )
    result = MerchantPayoutControl().evaluate([event], context)

    client.post(
        "/proofs/generate",
        json={
            "control_result": result.model_dump(mode="json"),
            "context": context.model_dump(mode="json"),
            "events": [event.model_dump(mode="json")],
            "proof_id": "api-tamper-check",
        },
    )

    tampered = _make_event("api-single", EventType.PAYMENT, "99.99")
    verify_resp = client.post(
        "/proofs/api-tamper-check/verify",
        json={"events": [tampered.model_dump(mode="json")]},
    )
    assert verify_resp.status_code == 200
    v_body = verify_resp.json()
    assert v_body["valid"] is False
    assert v_body["failure_reason"] == "EVENT_TAMPERED"
    assert v_body["tampering_detected"] is True


# ==============================================================================
# H. Investigation Decoupling & Explicit Proof Attachment (Correction 3)
# ==============================================================================


def test_investigation_proof_attachment_explicit_only(proof_env) -> None:
    """Correction 3: Proofs are not generated automatically; explicit attach_proof."""
    controller: FinanceController = proof_env["controller"]
    service: ControlProofService = proof_env["service"]
    event_repo: FinancialEventRepository = proof_env["event_repo"]

    events = [
        _make_event("inv-pay-1", EventType.PAYMENT, "10000.00"),
    ]
    for ev in events:
        event_repo.create_event(ev)

    context = MerchantPayoutContext(
        merchant_id="merchant-1",
        period_start=START,
        period_end=START + timedelta(hours=1),
        currency="INR",
    )
    control_result = MerchantPayoutControl().evaluate(events, context)

    # Investigation with anomaly
    analysis = ResidualIntelligenceEngine().analyze(
        [ResidualObservation(
            residual_id="res-1",
            control_id="merchant_payout_entitlement",
            domain=ControlDomain.MERCHANT_PAYOUT,
            timestamp=START,
            expected_amount=control_result.expected_amount,
            actual_amount=control_result.actual_amount,
            residual_amount=control_result.residual_amount,
            currency="INR",
            status=control_result.status,
        )],
        baseline_residuals=[ResidualObservation(
            residual_id="res-b",
            control_id="merchant_payout_entitlement",
            domain=ControlDomain.MERCHANT_PAYOUT,
            timestamp=START,
            expected_amount=Decimal("0.00"),
            actual_amount=Decimal("0.00"),
            residual_amount=Decimal("0.00"),
            currency="INR",
            status=ControlStatus.PASS,
        )],
    )

    request = InvestigationRequest(
        investigation_id="inv-attach-test",
        control_id="merchant_payout_entitlement",
        domain=ControlDomain.MERCHANT_PAYOUT,
        entity_id="entity-1",
        account_id="account-1",
        merchant_id="merchant-1",
        period_start=START,
        period_end=START + timedelta(hours=1),
        control_result=control_result,
        anomaly_score=analysis.anomaly_score,
        residual_summary=analysis,
    )

    report = controller.investigate(request)

    # 1. Verify investigation completed with verified root cause
    assert report.status.value == "COMPLETED"
    assert report.root_causes[0].category.value == "MISSING_EVENT"

    # 2. Verify no proof was automatically generated or fabricated
    assert report.proof_id is None
    assert report.merkle_root is None
    assert report.proof_status is None

    # 3. Generate a valid proof explicitly for this control result
    proof = service.generate_proof(control_result, context, events, proof_id="proof-for-inv")

    # 4. Explicitly attach the proof to the investigation
    updated_report = controller.attach_proof("inv-attach-test", "proof-for-inv")
    assert updated_report.proof_id == "proof-for-inv"
    assert updated_report.merkle_root == proof.merkle_root
    assert updated_report.proof_status == "VALID"



def test_cannot_attach_proof_to_inconclusive_investigation(proof_env) -> None:
    controller: FinanceController = proof_env["controller"]
    service: ControlProofService = proof_env["service"]

    # Investigation with no events in repo -> INCONCLUSIVE
    analysis = ResidualIntelligenceEngine().analyze(
        [ResidualObservation(
            residual_id="res-inc",
            control_id="settlement_control",
            domain=ControlDomain.SETTLEMENT,
            timestamp=START,
            expected_amount=Decimal("100.00"),
            actual_amount=Decimal("90.00"),
            residual_amount=Decimal("-10.00"),
            currency="INR",
            status=ControlStatus.FAIL,
        )],
        baseline_residuals=[ResidualObservation(
            residual_id="res-inc-b",
            control_id="settlement_control",
            domain=ControlDomain.SETTLEMENT,
            timestamp=START,
            expected_amount=Decimal("0.00"),
            actual_amount=Decimal("0.00"),
            residual_amount=Decimal("0.00"),
            currency="INR",
            status=ControlStatus.PASS,
        )],
    )
    control_result = ControlResult(
        control_id="settlement_control",
        domain=ControlDomain.SETTLEMENT,
        period_start=START,
        period_end=START + timedelta(hours=1),
        expected_amount=Decimal("100.00"),
        actual_amount=Decimal("90.00"),
        residual_amount=Decimal("-10.00"),
        currency="INR",
        status=ControlStatus.FAIL,
        tolerance=Decimal("0.00"),
        explanation="test",
    )
    request = InvestigationRequest(
        investigation_id="inv-inconclusive",
        control_id="settlement_control",
        domain=ControlDomain.SETTLEMENT,
        period_start=START,
        period_end=START + timedelta(hours=1),
        control_result=control_result,
        anomaly_score=analysis.anomaly_score,
        residual_summary=analysis,
    )
    report = controller.investigate(request)
    assert report.status.value == "INCONCLUSIVE"

    with pytest.raises(ValueError, match="cannot attach proof to an inconclusive investigation"):
        controller.attach_proof("inv-inconclusive", "some-proof-id")
