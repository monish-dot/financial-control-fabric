# Financial Control Fabric

Production-oriented prototype foundation for deterministic financial controls.

## Canonical event model

`FinancialEvent` is the shared Pydantic contract for normalized financial
events. It uses `Decimal` for amounts and supports the event types needed by
the five control domains.

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

## Financial control kernel

Phase 2 adds five deterministic controls. Each implements the same
`evaluate(events, context)` interface and returns a `ControlResult` containing
expected amount, actual amount, residual, tolerance, status, explanation, and
metadata:

- `NODAL_ESCROW`
- `SETTLEMENT`
- `MERCHANT_PAYOUT`
- `REVENUE_RECOGNITION`
- `CROSS_ENTITY`

Financial arithmetic uses `Decimal` only. A control rejects mixed currencies
instead of silently aggregating them. Control evaluation is read-only.

The control API is:

- `GET /controls` — list registered controls
- `GET /controls/{domain}` — inspect one control definition
- `POST /controls/evaluate/{domain}` — evaluate a control using a typed
  context and optional event collection

If `events` is omitted from an evaluation request, the endpoint evaluates the
events currently in the SQLite event store. Revenue recognition requires an
explicit expected recognition amount; cash events are not treated as
recognized revenue automatically.

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

Anomaly analysis, AI investigation, cryptographic proofs, frontends, external
APIs, and transaction-level reconciliation optimization are intentionally not
implemented yet.