"""Repository interfaces for persisted domain data."""

from backend.repositories.financial_event import (
    CreateEventResult,
    FinancialEventRepository,
)

__all__ = ["CreateEventResult", "FinancialEventRepository"]