"""Tamper-evident cryptographic control proof engine.

This package provides deterministic canonical event serialization, standard SHA-256
binary Merkle trees with odd-leaf duplication, and cryptographic control proof
generation and independent verification against the Financial Control Kernel.
"""

from backend.proof.generator import ControlProofGenerator
from backend.proof.hashing import (
    EMPTY_TREE_ROOT,
    canonical_event_bytes,
    canonical_event_dict,
    canonical_event_hash,
    canonical_sort_events,
    hash_pair,
)
from backend.proof.merkle import MerkleTree, verify_membership
from backend.proof.models import (
    ControlProof,
    MerkleMembershipProof,
    MerkleProofStep,
    ProofGenerationRequest,
    ProofVerificationRequest,
    ProofVerificationResult,
    VerificationFailureReason,
)
from backend.proof.repository import ControlProofRepository
from backend.proof.service import ControlProofService
from backend.proof.verifier import ControlProofVerifier

__all__ = [
    "ControlProof",
    "ProofVerificationResult",
    "VerificationFailureReason",
    "MerkleProofStep",
    "MerkleMembershipProof",
    "ProofGenerationRequest",
    "ProofVerificationRequest",
    "ControlProofGenerator",
    "ControlProofVerifier",
    "ControlProofRepository",
    "ControlProofService",
    "MerkleTree",
    "verify_membership",
    "canonical_sort_events",
    "canonical_event_dict",
    "canonical_event_bytes",
    "canonical_event_hash",
    "hash_pair",
    "EMPTY_TREE_ROOT",
]