"""FastAPI application entrypoint."""

from fastapi import FastAPI

from backend.models.financial_event import FinancialEvent

app = FastAPI(
    title="Financial Control Fabric",
    description="Initial API surface for deterministic financial controls.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Return the service health status."""

    return {"status": "ok"}


__all__ = ["app", "FinancialEvent"]