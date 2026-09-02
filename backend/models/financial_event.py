"""Canonical financial event model.

This module contains the shared event contract only. Domain-specific control
logic belongs in the controls and reconciliation packages.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventType(StrEnum):
    """Supported canonical financial event types."""

    PAYMENT = "PAYMENT"
    REFUND = "REFUND"
    PAYOUT = "PAYOUT"
    SETTLEMENT = "SETTLEMENT"
    FEE = "FEE"
    TAX = "TAX"
    ADJUSTMENT = "ADJUSTMENT"
    BANK_CREDIT = "BANK_CREDIT"
    BANK_DEBIT = "BANK_DEBIT"
    JOURNAL_ENTRY = "JOURNAL_ENTRY"
    REVENUE_RECOGNITION = "REVENUE_RECOGNITION"
    INTERCOMPANY_TRANSFER = "INTERCOMPANY_TRANSFER"


class FinancialEvent(BaseModel):
    """A normalized event emitted by a financial source system.

    The model intentionally describes event data without applying
    domain-specific reconciliation or accounting rules.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    event_id: str = Field(min_length=1)
    event_type: EventType
    source_system: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    merchant_id: str | None = None
    partner_id: str | None = None
    amount: Decimal
    currency: str = Field(min_length=3, max_length=3)
    event_timestamp: datetime
    effective_timestamp: datetime
    status: str = Field(min_length=1)
    parent_event_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def currency_must_be_uppercase(cls, value: str) -> str:
        """Require the canonical three-letter uppercase representation."""

        if not value.isalpha() or not value.isupper():
            raise ValueError("currency must be a three-letter uppercase code")
        return value