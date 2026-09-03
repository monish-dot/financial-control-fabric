"""Typed contracts for tamper-evident cryptographic control proofs."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.controls.models import ControlDomain, ControlResult, ControlStatus
from backend.models.financial_event import FinancialEvent


class VerificationFailureReason(StrEnum):
    """Categorized cryptographic and control verification outcomes."""

    VALID = "VALID"
    EVENT_TAMPERED = "EVENT_TAMPERED"
    EVENT_MISSING = "EVENT_MISSING"
    EVENT_ADDED = "EVENT_ADDED"
    CONTROL_RESULT_MISMATCH = "CONTROL_RESULT_MISMATCH"
    INVALID_PROOF = "INVALID_PROOF"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class MerkleProofStep(BaseModel):
    """One sibling hash step in a Merkle membership proof path."""

    model_config = ConfigDict(extra="forbid")

    sibling_hash: str = Field(min_length=64, max_length=64)
    position: str = Field(pattern="^(LEFT|RIGHT)$")


class MerkleMembershipProof(BaseModel):
    """Proof of inclusion for a specific financial event in a committed Merkle root."""

    model_config = ConfigDict(extra="forbid")

    proof_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    leaf_hash: str = Field(min_length=64, max_length=64)
    merkle_root: str = Field(min_length=64, max_length=64)
    proof_steps: list[MerkleProofStep] = Field(default_factory=list)
    verified: bool


class ControlProof(BaseModel):
    """Tamper-evident cryptographic binding of a control evaluation to its event set."""

    model_config = ConfigDict(extra="forbid")

    proof_id: str = Field(min_length=1)
    control_id: str = Field(min_length=1)
    domain: ControlDomain
    entity_id: str | None = None
    period_start: datetime
    period_end: datetime
    event_count: int = Field(ge=0)
    event_ids: list[str] = Field(default_factory=list)
    merkle_root: str = Field(min_length=64, max_length=64)
    control_status: ControlStatus
    expected_amount: Decimal
    actual_amount: Decimal
    residual_amount: Decimal
    currency: str = Field(min_length=3, max_length=3)
    context: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def currency_must_be_uppercase(cls, value: str) -> str:
        if not value.isalpha() or not value.isupper():
            raise ValueError("currency must be a three-letter uppercase code")
        return value

    @model_validator(mode="after")
    def validate_amounts_and_counts(self) -> "ControlProof":
        if self.residual_amount != self.actual_amount - self.expected_amount:
            raise ValueError("residual_amount must equal actual_amount - expected_amount")
        if self.event_count != len(self.event_ids):
            raise ValueError("event_count must match event_ids length")
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        return self


class ProofVerificationResult(BaseModel):
    """Detailed cryptographic and control invariant verification report."""

    model_config = ConfigDict(extra="forbid")

    proof_id: str = Field(min_length=1)
    valid: bool
    merkle_root_expected: str
    merkle_root_computed: str
    event_count_expected: int = Field(ge=0)
    event_count_computed: int = Field(ge=0)
    control_result_consistent: bool
    tampering_detected: bool
    failure_reason: VerificationFailureReason
    recomputed_result: ControlResult | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProofGenerationRequest(BaseModel):
    """Request to generate a cryptographic control proof."""

    model_config = ConfigDict(extra="forbid")

    control_result: ControlResult
    context: dict[str, Any] = Field(default_factory=dict)
    events: list[FinancialEvent] | None = None
    proof_id: str | None = None


class ProofVerificationRequest(BaseModel):
    """Request to verify a stored cryptographic control proof."""

    model_config = ConfigDict(extra="forbid")

    events: list[FinancialEvent] | None = None
