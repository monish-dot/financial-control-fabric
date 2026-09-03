"""Deterministic binary Merkle tree with documented odd-leaf handling."""

from collections.abc import Sequence

from backend.models.financial_event import FinancialEvent
from backend.proof.hashing import (
    EMPTY_TREE_ROOT,
    canonical_event_hash,
    canonical_sort_events,
    hash_pair,
)
from backend.proof.models import MerkleProofStep


class MerkleTree:
    """Deterministic binary Merkle tree.

    Canonical Rules:
    1. Events are sorted by (event_timestamp_UTC, event_id).
    2. Leaves are SHA-256 digests of canonically serialized events.
    3. If an intermediate level has an odd number of hashes (N > 1, N % 2 == 1),
       the final hash is duplicated before computing parent pairs.
    4. Parent = SHA-256(left_digest_bytes || right_digest_bytes).
    5. An empty tree produces the standard EMPTY_TREE_ROOT (SHA-256 of empty bytes).
    6. A single-leaf tree has its root equal to the single leaf digest.
    """

    def __init__(self, leaves: Sequence[str]) -> None:
        self.leaves: list[str] = list(leaves)
        self.levels: list[list[str]] = []
        self.root: str = self._build()

    @classmethod
    def from_events(cls, events: Sequence[FinancialEvent]) -> "MerkleTree":
        """Order events canonically and construct the Merkle tree."""

        sorted_events = canonical_sort_events(events)
        leaves = [canonical_event_hash(event) for event in sorted_events]
        return cls(leaves)

    def _build(self) -> str:
        if not self.leaves:
            return EMPTY_TREE_ROOT
        if len(self.leaves) == 1:
            self.levels = [[self.leaves[0]]]
            return self.leaves[0]

        current = list(self.leaves)
        self.levels = [list(current)]

        while len(current) > 1:
            if len(current) % 2 == 1:
                current.append(current[-1])
            next_level: list[str] = []
            for i in range(0, len(current), 2):
                next_level.append(hash_pair(current[i], current[i + 1]))
            self.levels.append(list(next_level))
            current = next_level

        return self.levels[-1][0]

    def generate_membership_proof(self, leaf_index: int) -> list[MerkleProofStep]:
        """Generate the sibling path from leaf to root for the specified leaf index."""

        if leaf_index < 0 or leaf_index >= len(self.leaves):
            raise IndexError(f"leaf_index {leaf_index} out of range [0, {len(self.leaves)})")
        if len(self.leaves) <= 1:
            return []

        steps: list[MerkleProofStep] = []
        current_index = leaf_index

        for level_idx in range(len(self.levels) - 1):
            level = list(self.levels[level_idx])
            if len(level) % 2 == 1:
                level.append(level[-1])

            if current_index % 2 == 0:
                sibling = level[current_index + 1]
                steps.append(MerkleProofStep(sibling_hash=sibling, position="RIGHT"))
            else:
                sibling = level[current_index - 1]
                steps.append(MerkleProofStep(sibling_hash=sibling, position="LEFT"))

            current_index //= 2

        return steps


def verify_membership(
    leaf_hash: str,
    proof_steps: Sequence[MerkleProofStep],
    expected_root: str,
) -> bool:
    """Independently verify an event's membership against an expected Merkle root."""

    current = leaf_hash
    for step in proof_steps:
        if step.position == "RIGHT":
            current = hash_pair(current, step.sibling_hash)
        elif step.position == "LEFT":
            current = hash_pair(step.sibling_hash, current)
        else:
            return False
    return current == expected_root
