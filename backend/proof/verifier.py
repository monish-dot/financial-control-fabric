"""Deterministic cryptographic control proof verification."""

from collections.abc import Sequence

from backend.controls.models import (
    ControlContext,
    ControlDomain,
    CrossEntityContext,
    MerchantPayoutContext,
    NodalEscrowContext,
    RevenueRecognitionContext,
    SettlementContext,
)
from backend.controls.registry import ControlRegistry, build_default_registry
from backend.models.financial_event import FinancialEvent
from backend.proof.hashing import canonical_sort_events
from backend.proof.merkle import MerkleTree
from backend.proof.models import (
    ControlProof,
    ProofVerificationResult,
    VerificationFailureReason,
)

CONTEXT_MODELS: dict[ControlDomain, type[ControlContext]] = {
    ControlDomain.NODAL_ESCROW: NodalEscrowContext,
    ControlDomain.SETTLEMENT: SettlementContext,
    ControlDomain.MERCHANT_PAYOUT: MerchantPayoutContext,
    ControlDomain.REVENUE_RECOGNITION: RevenueRecognitionContext,
    ControlDomain.CROSS_ENTITY: CrossEntityContext,
}


class ControlProofVerifier:
    """Verify proof integrity and independently recompute control results via the kernel."""

    def __init__(self, control_registry: ControlRegistry | None = None) -> None:
        self._registry = control_registry or build_default_registry()

    def verify(
        self,
        proof: ControlProof,
        events: Sequence[FinancialEvent],
    ) -> ProofVerificationResult:
        """Verify the event set, Merkle root, and re-evaluated control invariant.

        The verifier re-runs the existing Financial Control Kernel deterministically
        over the verified event set and compares the newly computed control result
        against the committed proof amounts and status.
        """

        try:
            # 1. Basic proof structure check
            if proof.event_count != len(proof.event_ids) or proof.period_end < proof.period_start:
                return self._failure(
                    proof,
                    events,
                    computed_root="",
                    reason=VerificationFailureReason.INVALID_PROOF,
                    detail="Invalid proof metadata or event count discrepancy",
                )

            event_id_set = {event.event_id for event in events}
            proof_id_set = set(proof.event_ids)

            # 2. Missing events check
            missing_ids = sorted(proof_id_set - event_id_set)
            if missing_ids:
                return self._failure(
                    proof,
                    events,
                    computed_root="",
                    reason=VerificationFailureReason.EVENT_MISSING,
                    detail=f"Events missing from verification set: {', '.join(missing_ids)}",
                )

            # 3. Added events check
            added_ids = sorted(event_id_set - proof_id_set)
            if added_ids:
                return self._failure(
                    proof,
                    events,
                    computed_root="",
                    reason=VerificationFailureReason.EVENT_ADDED,
                    detail=f"Unexpected events present in verification set: {', '.join(added_ids)}",
                )

            # 4. Canonical normalization and Merkle tree reconstruction
            sorted_events = canonical_sort_events(events)
            computed_tree = MerkleTree.from_events(sorted_events)

            if computed_tree.root != proof.merkle_root:
                return self._failure(
                    proof,
                    sorted_events,
                    computed_root=computed_tree.root,
                    reason=VerificationFailureReason.EVENT_TAMPERED,
                    detail=(
                        f"Computed Merkle root {computed_tree.root} does not match "
                        f"committed root {proof.merkle_root}; event content was altered"
                    ),
                )

            # 5. Financial Control Kernel re-evaluation (Single source of financial truth)
            context_model = CONTEXT_MODELS.get(proof.domain)
            if context_model is None:
                return self._failure(
                    proof,
                    sorted_events,
                    computed_root=computed_tree.root,
                    reason=VerificationFailureReason.INVALID_PROOF,
                    detail=f"Unknown control domain: {proof.domain}",
                )

            try:
                context = context_model.model_validate(proof.context)
                recomputed_result = self._registry.evaluate(
                    proof.domain, sorted_events, context
                )
            except Exception as exc:
                return self._failure(
                    proof,
                    sorted_events,
                    computed_root=computed_tree.root,
                    reason=VerificationFailureReason.CONTROL_RESULT_MISMATCH,
                    detail=f"Failed to re-evaluate control via kernel: {exc}",
                )

            # 6. Compare recomputed control result with committed proof values
            result_matches = (
                recomputed_result.expected_amount == proof.expected_amount
                and recomputed_result.actual_amount == proof.actual_amount
                and recomputed_result.residual_amount == proof.residual_amount
                and recomputed_result.currency == proof.currency
                and recomputed_result.status == proof.control_status
            )

            if not result_matches:
                mismatches = []
                if recomputed_result.expected_amount != proof.expected_amount:
                    mismatches.append(
                        f"expected: recomputed {recomputed_result.expected_amount} != proof {proof.expected_amount}"
                    )
                if recomputed_result.actual_amount != proof.actual_amount:
                    mismatches.append(
                        f"actual: recomputed {recomputed_result.actual_amount} != proof {proof.actual_amount}"
                    )
                if recomputed_result.residual_amount != proof.residual_amount:
                    mismatches.append(
                        f"residual: recomputed {recomputed_result.residual_amount} != proof {proof.residual_amount}"
                    )
                if recomputed_result.currency != proof.currency:
                    mismatches.append(
                        f"currency: recomputed {recomputed_result.currency} != proof {proof.currency}"
                    )
                if recomputed_result.status != proof.control_status:
                    mismatches.append(
                        f"status: recomputed {recomputed_result.status} != proof {proof.control_status}"
                    )

                return self._failure(
                    proof,
                    sorted_events,
                    computed_root=computed_tree.root,
                    reason=VerificationFailureReason.CONTROL_RESULT_MISMATCH,
                    detail=f"Re-evaluated control result differs from proof: {'; '.join(mismatches)}",
                    recomputed_result=recomputed_result,
                )

            # All checks succeeded
            return ProofVerificationResult(
                proof_id=proof.proof_id,
                valid=True,
                merkle_root_expected=proof.merkle_root,
                merkle_root_computed=computed_tree.root,
                event_count_expected=proof.event_count,
                event_count_computed=len(sorted_events),
                control_result_consistent=True,
                tampering_detected=False,
                failure_reason=VerificationFailureReason.VALID,
                recomputed_result=recomputed_result,
                metadata={
                    "status": "VALID",
                    "canonical_event_ordering": "normalized",
                    "kernel_recomputed": True,
                },
            )

        except Exception as error:
            return self._failure(
                proof,
                events,
                computed_root="",
                reason=VerificationFailureReason.UNKNOWN_ERROR,
                detail=f"Unexpected error during verification: {error}",
            )

    def _failure(
        self,
        proof: ControlProof,
        events: Sequence[FinancialEvent],
        *,
        computed_root: str,
        reason: VerificationFailureReason,
        detail: str,
        recomputed_result=None,
    ) -> ProofVerificationResult:
        tampering = reason in {
            VerificationFailureReason.EVENT_TAMPERED,
            VerificationFailureReason.EVENT_MISSING,
            VerificationFailureReason.EVENT_ADDED,
        }
        return ProofVerificationResult(
            proof_id=proof.proof_id,
            valid=False,
            merkle_root_expected=proof.merkle_root,
            merkle_root_computed=computed_root,
            event_count_expected=proof.event_count,
            event_count_computed=len(events),
            control_result_consistent=(reason is not VerificationFailureReason.CONTROL_RESULT_MISMATCH),
            tampering_detected=tampering,
            failure_reason=reason,
            recomputed_result=recomputed_result,
            metadata={"detail": detail},
        )
