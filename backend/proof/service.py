"""Cryptographic control proof orchestration service."""

from collections.abc import Sequence
from typing import Any

from backend.controls.models import ControlContext, ControlResult
from backend.controls.registry import ControlRegistry
from backend.models.financial_event import FinancialEvent
from backend.proof.generator import ControlProofGenerator
from backend.proof.hashing import canonical_event_hash, canonical_sort_events
from backend.proof.merkle import MerkleTree, verify_membership
from backend.proof.models import (
    ControlProof,
    MerkleMembershipProof,
    ProofVerificationResult,
    VerificationFailureReason,
)
from backend.proof.repository import ControlProofRepository
from backend.proof.verifier import ControlProofVerifier
from backend.repositories.financial_event import FinancialEventRepository


class ControlProofService:
    """Orchestrate proof generation, verification, and membership queries."""

    def __init__(
        self,
        repository: ControlProofRepository,
        event_repository: FinancialEventRepository | None = None,
        control_registry: ControlRegistry | None = None,
    ) -> None:
        self._repository = repository
        self._event_repository = event_repository
        self._generator = ControlProofGenerator()
        self._verifier = ControlProofVerifier(control_registry)

    def generate_proof(
        self,
        control_result: ControlResult,
        context: ControlContext | dict[str, Any],
        events: Sequence[FinancialEvent] | None = None,
        *,
        proof_id: str | None = None,
    ) -> ControlProof:
        """Generate, persist, and return a tamper-evident ControlProof.

        Does not modify financial events or ledger balances.
        """

        if events is None:
            if self._event_repository is None:
                raise ValueError("event_repository required when events not supplied")
            events = self._event_repository.list_events()

        proof = self._generator.generate(
            control_result=control_result,
            context=context,
            events=events,
            proof_id=proof_id,
        )
        return self._repository.create_proof(proof)

    def get_proof(self, proof_id: str) -> ControlProof | None:
        """Retrieve a stored control proof by ID."""

        return self._repository.get_proof(proof_id)

    def verify_proof(
        self,
        proof_id: str,
        events: Sequence[FinancialEvent] | None = None,
    ) -> ProofVerificationResult:
        """Verify proof integrity and recompute control invariant via the kernel."""

        proof = self._repository.get_proof(proof_id)
        if proof is None:
            return ProofVerificationResult(
                proof_id=proof_id,
                valid=False,
                merkle_root_expected="",
                merkle_root_computed="",
                event_count_expected=0,
                event_count_computed=0,
                control_result_consistent=False,
                tampering_detected=False,
                failure_reason=VerificationFailureReason.INVALID_PROOF,
                metadata={"detail": f"proof '{proof_id}' not found"},
            )

        if events is None:
            if self._event_repository is None:
                raise ValueError("event_repository required when events not supplied")
            events = []
            for event_id in proof.event_ids:
                event = self._event_repository.get_event(event_id)
                if event is not None:
                    events.append(event)

        return self._verifier.verify(proof, events)

    def get_membership_proof(
        self,
        proof_id: str,
        event_id: str,
        events: Sequence[FinancialEvent] | None = None,
    ) -> MerkleMembershipProof:
        """Generate a Merkle membership proof for an event in the committed proof."""

        proof = self._repository.get_proof(proof_id)
        if proof is None:
            raise ValueError(f"proof '{proof_id}' not found")

        if event_id not in proof.event_ids:
            raise ValueError(f"event '{event_id}' not present in proof '{proof_id}'")

        if events is None:
            if self._event_repository is None:
                raise ValueError("event_repository required when events not supplied")
            events = []
            for eid in proof.event_ids:
                evt = self._event_repository.get_event(eid)
                if evt is not None:
                    events.append(evt)

        sorted_events = canonical_sort_events(events)
        target_event = None
        target_index = -1
        for idx, evt in enumerate(sorted_events):
            if evt.event_id == event_id:
                target_event = evt
                target_index = idx
                break

        if target_event is None or target_index < 0:
            raise ValueError(f"event '{event_id}' could not be resolved from event set")

        leaf_hash = canonical_event_hash(target_event)
        tree = MerkleTree.from_events(sorted_events)
        proof_steps = tree.generate_membership_proof(target_index)
        verified = verify_membership(leaf_hash, proof_steps, proof.merkle_root)

        return MerkleMembershipProof(
            proof_id=proof_id,
            event_id=event_id,
            leaf_hash=leaf_hash,
            merkle_root=proof.merkle_root,
            proof_steps=proof_steps,
            verified=verified,
        )
