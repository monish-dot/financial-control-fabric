"""Deterministic control proof generation service."""

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any
import uuid

from backend.controls.models import ControlContext, ControlResult
from backend.models.financial_event import FinancialEvent
from backend.proof.hashing import canonical_sort_events
from backend.proof.merkle import MerkleTree
from backend.proof.models import ControlProof


class ControlProofGenerator:
    """Generate a tamper-evident cryptographic proof binding events to a control result."""

    def generate(
        self,
        control_result: ControlResult,
        context: ControlContext | dict[str, Any],
        events: Sequence[FinancialEvent],
        *,
        proof_id: str | None = None,
        generated_at: datetime | None = None,
    ) -> ControlProof:
        """Construct a deterministic ControlProof from a control result and its event set.

        The operation is strictly read-only and will not mutate financial events.
        """

        context_dict = (
            context.model_dump(mode="json")
            if isinstance(context, ControlContext)
            else dict(context)
        )
        sorted_events = canonical_sort_events(events)
        tree = MerkleTree.from_events(sorted_events)
        event_ids = [event.event_id for event in sorted_events]
        effective_proof_id = proof_id or f"proof_{uuid.uuid4().hex[:16]}"
        timestamp = generated_at or datetime.now(timezone.utc)

        algorithm_metadata = {
            "proof_type": "TAMPER_EVIDENT_CONTROL_PROOF",
            "hash_algorithm": "SHA-256",
            "tree_type": "binary_merkle",
            "serialization": "canonical_json_v1",
            "odd_leaf_rule": "duplicate_final_leaf",
            "sorting_rule": "event_timestamp_asc_event_id_asc",
            "version": "1.0.0",
        }

        return ControlProof(
            proof_id=effective_proof_id,
            control_id=control_result.control_id,
            domain=control_result.domain,
            entity_id=control_result.entity_id,
            period_start=control_result.period_start,
            period_end=control_result.period_end,
            event_count=len(sorted_events),
            event_ids=event_ids,
            merkle_root=tree.root,
            control_status=control_result.status,
            expected_amount=control_result.expected_amount,
            actual_amount=control_result.actual_amount,
            residual_amount=control_result.residual_amount,
            currency=control_result.currency,
            context=context_dict,
            generated_at=timestamp,
            metadata=algorithm_metadata,
        )
