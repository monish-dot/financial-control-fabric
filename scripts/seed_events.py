"""Seed the local SQLite event store with deterministic synthetic events."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.database import Database
from backend.models.financial_event import EventType, FinancialEvent
from backend.repositories import FinancialEventRepository


def build_seed_events() -> list[FinancialEvent]:
    """Build thirty deterministic INR events across all supported types."""

    start = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    event_types = list(EventType)
    events: list[FinancialEvent] = []

    for index in range(30):
        event_type = event_types[index % len(event_types)]
        timestamp = start + timedelta(hours=index * 6)
        events.append(
            FinancialEvent(
                event_id=f"seed_evt_{index + 1:03d}",
                event_type=event_type,
                source_system="synthetic_seed",
                source_id=f"seed_source_{index + 1:03d}",
                entity_id=f"entity_{index % 3 + 1:03d}",
                account_id=f"account_{index % 4 + 1:03d}",
                merchant_id=f"merchant_{index % 5 + 1:03d}",
                partner_id=f"partner_{index % 2 + 1:03d}",
                amount=Decimal(f"{100 + index * 17}.{index % 100:02d}"),
                currency="INR",
                event_timestamp=timestamp,
                effective_timestamp=timestamp,
                status="posted",
                metadata={"synthetic": True, "seed_index": index + 1},
            )
        )

    return events


def seed() -> tuple[int, int]:
    """Insert seed events idempotently and return created/existing counts."""

    database = Database()
    database.initialize()
    repository = FinancialEventRepository(database.session_factory)
    created = 0
    existing = 0

    for event in build_seed_events():
        result = repository.create_event(event)
        if result.created:
            created += 1
        else:
            existing += 1

    database.dispose()
    return created, existing


if __name__ == "__main__":
    created_count, existing_count = seed()
    print(f"Seed complete: {created_count} created, {existing_count} already existed.")