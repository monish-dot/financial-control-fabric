# Financial Control Fabric

Production-oriented prototype foundation for deterministic financial controls.

## Canonical event model

`FinancialEvent` is the shared Pydantic contract for normalized financial
events. It uses `Decimal` for amounts and supports the event types needed by
the future control domains. Domain-specific reconciliation and accounting
logic are intentionally not part of this phase.

## SQLite event store

Phase 1 persists canonical events in `data/financial_control.db` through a
SQLAlchemy repository. Amounts are stored as exact text representations so
SQLite never performs financial work with floating-point values. Duplicate
`event_id` submissions are idempotent and return the existing event.

## API endpoints

```bash
uvicorn backend.api.main:app --host 0.0.0.0 --port 5000
```

- `GET /health` — service health
- `POST /events` — create an event
- `GET /events/{event_id}` — retrieve one event
- `GET /events` — list events with optional `event_type`, `entity_id`,
  `account_id`, `merchant_id`, `limit`, and `offset` query parameters

FastAPI publishes the OpenAPI documentation at `/docs`.

## Synthetic seed data

The seed script creates 30 deterministic synthetic INR events across every
supported event type:

```bash
python -m scripts.seed_events
```

Running it again is safe because event creation is idempotent.

## Tests

```bash
pytest
```

Reconciliation, anomaly analysis, AI investigation, cryptographic proofs,
frontends, and external APIs are intentionally not implemented yet.