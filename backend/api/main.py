"""FastAPI application entrypoint."""

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from pydantic import BaseModel

from backend.database.connection import Database
from backend.models.financial_event import FinancialEvent
from backend.repositories.financial_event import FinancialEventRepository


class EventCreateResponse(BaseModel):
    """Response returned by idempotent event creation."""

    event: FinancialEvent
    created: bool
    message: str


def create_app(database: Database | None = None) -> FastAPI:
    """Create the API application with an injectable database."""

    database = database or Database()
    database.initialize()
    repository = FinancialEventRepository(database.session_factory)

    app = FastAPI(
        title="Financial Control Fabric",
        description="Deterministic canonical financial event store.",
        version="0.1.0",
    )

    def get_repository() -> FinancialEventRepository:
        return repository

    @app.get("/health")
    def health() -> dict[str, str]:
        """Return the service health status."""

        return {"status": "ok"}

    @app.post(
        "/events",
        response_model=EventCreateResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_event(
        event: FinancialEvent,
        response: Response,
        event_repository: FinancialEventRepository = Depends(get_repository),
    ) -> EventCreateResponse:
        """Create a canonical event, safely ignoring duplicate submissions."""

        result = event_repository.create_event(event)
        response.status_code = (
            status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
        )
        return EventCreateResponse(
            event=result.event,
            created=result.created,
            message="event created" if result.created else "event already exists",
        )

    @app.get("/events", response_model=list[FinancialEvent])
    def list_events(
        event_type: str | None = Query(default=None),
        entity_id: str | None = Query(default=None),
        account_id: str | None = Query(default=None),
        merchant_id: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
        event_repository: FinancialEventRepository = Depends(get_repository),
    ) -> list[FinancialEvent]:
        """List canonical events with optional filters and pagination."""

        return event_repository.list_events(
            event_type=event_type,
            entity_id=entity_id,
            account_id=account_id,
            merchant_id=merchant_id,
            limit=limit,
            offset=offset,
        )

    @app.get("/events/{event_id}", response_model=FinancialEvent)
    def get_event(
        event_id: str,
        event_repository: FinancialEventRepository = Depends(get_repository),
    ) -> FinancialEvent:
        """Retrieve one canonical event by ID."""

        event = event_repository.get_event(event_id)
        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"event '{event_id}' not found",
            )
        return event

    return app

app = create_app()

__all__ = ["app", "create_app", "EventCreateResponse", "FinancialEvent"]