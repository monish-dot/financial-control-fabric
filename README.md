# Financial Control Fabric

Initial production-oriented prototype foundation for deterministic financial
controls.

## Run locally

```bash
uvicorn backend.api.main:app --host 0.0.0.0 --port 5000
```

The health endpoint is available at `GET /health`.

## Test

```bash
pytest
```

The project currently contains only the canonical `FinancialEvent` model and
the health endpoint. Reconciliation, anomaly analysis, AI investigation, and
cryptographic proof logic are intentionally not implemented yet.