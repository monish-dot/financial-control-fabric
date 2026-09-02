"""Shared models for deterministic financial controls."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ControlDomain(StrEnum):
    """Registered financial-control domains."""

    NODAL_ESCROW = "NODAL_ESCROW"
    SETTLEMENT = "SETTLEMENT"
    MERCHANT_PAYOUT = "MERCHANT_PAYOUT"
    REVENUE_RECOGNITION = "REVENUE_RECOGNITION"
    CROSS_ENTITY = "CROSS_ENTITY"


class ControlStatus(StrEnum):
    """Deterministic control outcomes."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


class ControlResult(BaseModel):
    """Common output contract for every financial control."""

    model_config = ConfigDict(extra="forbid")

    control_id: str = Field(min_length=1)
    domain: ControlDomain
    entity_id: str | None = None
    period_start: datetime
    period_end: datetime
    expected_amount: Decimal
    actual_amount: Decimal
    residual_amount: Decimal
    currency: str = Field(min_length=3, max_length=3)
    status: ControlStatus
    tolerance: Decimal = Field(ge=Decimal("0"))
    explanation: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def currency_must_be_uppercase(cls, value: str) -> str:
        if not value.isalpha() or not value.isupper():
            raise ValueError("currency must be a three-letter uppercase code")
        return value

    @model_validator(mode="after")
    def residual_must_be_deterministic(self) -> "ControlResult":
        if self.residual_amount != self.actual_amount - self.expected_amount:
            raise ValueError("residual_amount must equal actual_amount - expected_amount")
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        return self


class ControlContext(BaseModel):
    """Shared scope and tolerance input for a control evaluation."""

    model_config = ConfigDict(extra="forbid")

    control_id: str | None = None
    entity_id: str | None = None
    account_id: str | None = None
    period_start: datetime
    period_end: datetime
    currency: str = Field(min_length=3, max_length=3)
    tolerance: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"))

    @field_validator("currency")
    @classmethod
    def currency_must_be_uppercase(cls, value: str) -> str:
        if not value.isalpha() or not value.isupper():
            raise ValueError("currency must be a three-letter uppercase code")
        return value

    @model_validator(mode="after")
    def period_must_be_ordered(self) -> "ControlContext":
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        return self


class NodalEscrowContext(ControlContext):
    """Inputs for the nodal/escrow balance invariant."""

    account_id: str = Field(min_length=1)
    opening_balance: Decimal
    actual_bank_balance: Decimal | None = None
    permitted_deductions: Decimal = Decimal("0.00")


class SettlementContext(ControlContext):
    """Inputs for aggregate multi-bank/multi-partner settlement control."""

    partner_id: str = Field(min_length=1)
    valid_timing_difference: Decimal = Decimal("0.00")


class MerchantPayoutContext(ControlContext):
    """Inputs for merchant payout entitlement control."""

    merchant_id: str = Field(min_length=1)


class RevenueRecognitionContext(ControlContext):
    """Deterministic recognition schedule input for revenue control."""

    expected_recognized_revenue: Decimal


class CrossEntityContext(ControlContext):
    """Source and destination scope for intercompany reconciliation."""

    source_entity_id: str = Field(min_length=1)
    destination_entity_id: str = Field(min_length=1)