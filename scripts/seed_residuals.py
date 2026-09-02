"""Seed the local residual store with deterministic synthetic populations."""

from backend.anomaly.residual_store import ResidualStore
from backend.database import Database
from data.residual_scenarios import build_residual_populations


def seed() -> tuple[int, int]:
    """Insert all synthetic residual populations idempotently."""

    database = Database()
    database.initialize()
    store = ResidualStore(database.session_factory)
    created = 0
    existing = 0
    for observations in build_residual_populations().values():
        for observation in observations:
            current = store.get_residual(observation.residual_id)
            if current is None:
                store.record_residual(observation)
                created += 1
            else:
                existing += 1
    database.dispose()
    return created, existing


if __name__ == "__main__":
    created_count, existing_count = seed()
    print(
        f"Residual seed complete: {created_count} created, "
        f"{existing_count} already existed."
    )