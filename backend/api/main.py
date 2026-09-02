"""FastAPI application entrypoint."""

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, ValidationError

from backend.controls.cross_entity import CrossEntityControl
from backend.controls.merchant_payout import MerchantPayoutControl
from backend.controls.models import (
    ControlContext,
    ControlDomain,
    ControlResult,
    CrossEntityContext,
    MerchantPayoutContext,
    NodalEscrowContext,
    RevenueRecognitionContext,
    SettlementContext,
)
from backend.controls.nodal_escrow import NodalEscrowControl
from backend.controls.registry import ControlRegistry, build_default_registry
from backend.controls.revenue_recognition import RevenueRecognitionControl
from backend.controls.settlement import SettlementControl
from backend.database.connection import Database
from backend.models.financial_event import FinancialEvent
from backend.repositories.financial_event import FinancialEventRepository


class EventCreateResponse(BaseModel):
    """Response returned by idempotent event creation."""

    event: FinancialEvent
    created: bool
    message: str


class ControlDefinition(BaseModel):
    """Public description of a registered financial control."""

    domain: ControlDomain
    control_id: str
    description: str


class ControlEvaluationRequest(BaseModel):
    """Read-only control input containing events and a domain context."""

    events: list[FinancialEvent] | None = None
    context: dict[str, Any] = Field(default_factory=dict)


CONTEXT_MODELS: dict[ControlDomain, type[ControlContext]] = {
    ControlDomain.NODAL_ESCROW: NodalEscrowContext,
    ControlDomain.SETTLEMENT: SettlementContext,
    ControlDomain.MERCHANT_PAYOUT: MerchantPayoutContext,
    ControlDomain.REVENUE_RECOGNITION: RevenueRecognitionContext,
    ControlDomain.CROSS_ENTITY: CrossEntityContext,
}

CONTROL_DESCRIPTIONS: dict[ControlDomain, str] = {
    ControlDomain.NODAL_ESCROW: "Opening balance, event movements, and bank balance invariant.",
    ControlDomain.SETTLEMENT: "Aggregate multi-bank and multi-partner settlement obligation control.",
    ControlDomain.MERCHANT_PAYOUT: "Merchant entitlement less fees, taxes, refunds, and adjustments.",
    ControlDomain.REVENUE_RECOGNITION: "Expected recognition schedule versus recorded revenue recognition.",
    ControlDomain.CROSS_ENTITY: "Source-entity intercompany transfer versus destination journal entry.",
}


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

    def get_registry() -> ControlRegistry:
        return registry

    registry = build_default_registry()

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

    @app.get("/controls", response_model=list[ControlDefinition])
    def list_controls(
        control_registry: ControlRegistry = Depends(get_registry),
    ) -> list[ControlDefinition]:
        """List the deterministic controls available for evaluation."""

        return [
            ControlDefinition(
                domain=domain,
                control_id=control_registry.get(domain).control_id,
                description=CONTROL_DESCRIPTIONS[domain],
            )
            for domain in control_registry.domains()
        ]

    @app.post("/controls/evaluate/{domain}", response_model=ControlResult)
    def evaluate_control(
        domain: str,
        request: ControlEvaluationRequest,
        control_registry: ControlRegistry = Depends(get_registry),
        event_repository: FinancialEventRepository = Depends(get_repository),
    ) -> ControlResult:
        """Evaluate a registered control without modifying stored events."""

        try:
            normalized_domain = ControlDomain(domain.upper())
            context_model = CONTEXT_MODELS[normalized_domain]
            context = context_model.model_validate(request.context)
        except (KeyError, ValueError, ValidationError) as error:
            detail = error.errors() if isinstance(error, ValidationError) else str(error)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=detail,
            ) from error

        events = (
            request.events
            if request.events is not None
            else event_repository.list_events()
        )
        try:
            return control_registry.evaluate(normalized_domain, events, context)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            ) from error

    @app.get("/controls/{domain}", response_model=ControlDefinition)
    def get_control(
        domain: str,
        control_registry: ControlRegistry = Depends(get_registry),
    ) -> ControlDefinition:
        """Retrieve the definition of one registered control."""

        try:
            normalized_domain = ControlDomain(domain.upper())
            control = control_registry.get(normalized_domain)
        except (KeyError, ValueError) as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"control domain '{domain}' not found",
            ) from error
        return ControlDefinition(
            domain=normalized_domain,
            control_id=control.control_id,
            description=CONTROL_DESCRIPTIONS[normalized_domain],
        )

    return app

app = create_app()

__all__ = ["app", "create_app", "EventCreateResponse", "FinancialEvent"]