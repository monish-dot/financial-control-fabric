"""Typed models for constrained settlement reconciliation."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ReconciliationSide(StrEnum):
    INTERNAL = "INTERNAL"
    EXTERNAL = "EXTERNAL"


class ReconciliationItemType(StrEnum):
    SETTLEMENT_OBLIGATION = "SETTLEMENT_OBLIGATION"
    BANK_SETTLEMENT = "BANK_SETTLEMENT"
    PARTNER_CONFIRMATION = "PARTNER_CONFIRMATION"


class ReconciliationItem(BaseModel):
    """One obligation or external settlement record."""

    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1)
    side: ReconciliationSide
    item_type: ReconciliationItemType
    entity_id: str | None = None
    account_id: str | None = None
    merchant_id: str | None = None
    partner_id: str | None = None
    amount: Decimal = Field(ge=Decimal("0"))
    currency: str = Field(min_length=3, max_length=3)
    timestamp: datetime
    reference_id: str | None = None
    status: str = Field(default="OPEN", min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def currency_must_be_uppercase(cls, value: str) -> str:
        if not value.isalpha() or not value.isupper():
            raise ValueError("currency must be a three-letter uppercase code")
        return value


class ReconciliationConstraints(BaseModel):
    """Explicit matching constraints used by the optimizer."""

    model_config = ConfigDict(extra="forbid")

    timestamp_tolerance_minutes: int | None = Field(default=None, ge=0)
    normalize_references: bool = True
    require_reference_match: bool = False
    require_entity_match: bool = False
    require_account_match: bool = False
    require_merchant_match: bool = False
    require_partner_match: bool = False
    minimum_compatibility_score: Decimal = Field(
        default=Decimal("0"), ge=Decimal("0"), le=Decimal("1")
    )


class MatchAllocation(BaseModel):
    """One proposed amount allocated between an internal and external item."""

    model_config = ConfigDict(extra="forbid")

    allocation_id: str = Field(min_length=1)
    internal_item_id: str = Field(min_length=1)
    external_item_id: str = Field(min_length=1)
    allocated_amount: Decimal = Field(ge=Decimal("0"))
    currency: str = Field(min_length=3, max_length=3)
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    reason: str = Field(min_length=1)
    constraints_satisfied: bool
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def currency_must_be_uppercase(cls, value: str) -> str:
        if not value.isalpha() or not value.isupper():
            raise ValueError("currency must be a three-letter uppercase code")
        return value


class ReconciliationStatus(StrEnum):
    FULLY_RECONCILED = "FULLY_RECONCILED"
    PARTIALLY_RECONCILED = "PARTIALLY_RECONCILED"
    UNRECONCILED = "UNRECONCILED"


class ReconciliationResult(BaseModel):
    """Deterministic settlement reconciliation result."""

    model_config = ConfigDict(extra="forbid")

    reconciliation_id: str = Field(min_length=1)
    matched_amount: Decimal = Field(ge=Decimal("0"))
    unmatched_internal_amount: Decimal = Field(ge=Decimal("0"))
    unmatched_external_amount: Decimal = Field(ge=Decimal("0"))
    allocation_count: int = Field(ge=0)
    match_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    currency: str = Field(min_length=3, max_length=3)
    status: ReconciliationStatus
    allocations: list[MatchAllocation] = Field(default_factory=list)
    explanation: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def currency_must_be_uppercase(cls, value: str) -> str:
        if not value.isalpha() or not value.isupper():
            raise ValueError("currency must be a three-letter uppercase code")
        return value

    @model_validator(mode="after")
    def allocation_count_matches_allocations(self) -> "ReconciliationResult":
        if self.allocation_count != len(self.allocations):
            raise ValueError("allocation_count must match allocations length")
        return self