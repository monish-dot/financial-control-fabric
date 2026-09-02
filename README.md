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

## Residual distribution intelligence

Phase 3 preserves control outcomes as structured `ResidualObservation` records
in the separate `residual_observations` table. The analytical layer provides:

- Decimal-safe population statistics, including mean, median, p95, p99,
  absolute statistics, and positive/negative ratios
- KS, Wasserstein, and PSI distribution-shift metrics
- Rolling residual statistics and deterministic CUSUM drift detection
- Explainable multi-signal anomaly scores with `NORMAL`, `WATCH`, `ANOMALOUS`,
  and `CRITICAL` severity levels
- Persisted `ResidualBaseline` records for domain/entity/account windows

Residual analysis never changes financial events, balances, payouts, or
accounting entries. The read-only endpoints are:

- `GET /residuals`
- `GET /residuals/{residual_id}`
- `GET /residuals/distribution/{domain}`
- `GET /residuals/baseline/{domain}`
- `POST /residuals/analyze/{domain}`

Synthetic residual populations can be loaded with:

```bash
python -m scripts.seed_residuals
```

## Constrained reconciliation engine

Phase 4 adds deterministic many-to-many settlement reconciliation under
`backend/reconciliation/`. It uses Decimal amounts converted to integer minor
units for OR-Tools CP-SAT optimization, with a deterministic greedy fallback
when OR-Tools is unavailable.

The optimizer supports:

- one-to-one, many-to-one, one-to-many, and many-to-many allocations
- internal and external capacity limits
- currency isolation with no implicit FX conversion
- configurable timestamp windows
- normalized reference matching
- entity, account, merchant, and partner compatibility constraints
- explainable compatibility scores and allocation reasons
- deterministic repeated results and reconciliation IDs

The reconciliation layer only proposes allocations. It never modifies
financial events, balances, payouts, accounting entries, or settlement
approval state. A result can be adapted into the existing residual model with
the service integration point when a caller explicitly chooses to persist it.

The reconciliation API is:

- `POST /reconciliation/settlement`
- `GET /reconciliation/{reconciliation_id}`

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

AI investigation, cryptographic proofs, frontends, external APIs, and
autonomous financial actions are intentionally not implemented yet.