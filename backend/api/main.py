"""FastAPI application entrypoint."""

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, ValidationError

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
from backend.controls.registry import ControlRegistry, build_default_registry
from backend.anomaly.baseline import ResidualBaselineManager, ResidualBaselineStore
from backend.anomaly.distribution import (
    ResidualDistributionAnalyzer,
    ensure_single_currency,
)
from backend.anomaly.engine import ResidualIntelligenceEngine
from backend.anomaly.residual_models import (
    ResidualAnalysis,
    ResidualBaseline,
    ResidualDistributionStatistics,
    ResidualObservation,
)
from backend.anomaly.residual_store import ResidualStore
from backend.agent.investigator import FinanceController
from backend.agent.models import (
    AgentAuditEvent,
    ApprovalRequest,
    ControllerAction,
    EvidenceItem,
    InvestigationHypothesis,
    InvestigationReport,
    InvestigationRequest,
    RevalidationRequest,
    RevalidationResult,
)
from backend.database.connection import Database
from backend.models.financial_event import FinancialEvent
from backend.repositories.financial_event import FinancialEventRepository
from backend.reconciliation.models import (
    ReconciliationConstraints,
    ReconciliationItem,
    ReconciliationResult,
)
from backend.reconciliation.service import ReconciliationService


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


class ResidualAnalysisRequest(BaseModel):
    """Read-only residual analysis input."""

    residuals: list[ResidualObservation] | None = None
    baseline_residuals: list[ResidualObservation] | None = None
    baseline_id: str | None = None
    rolling_window: int = Field(default=5, ge=1, le=1000)
    currency: str | None = None


class ResidualDistributionResponse(BaseModel):
    """Statistics for one residual domain population."""

    domain: ControlDomain
    statistics: ResidualDistributionStatistics


class ReconciliationRequest(BaseModel):
    """Read-only many-to-many reconciliation input."""

    internal_items: list[ReconciliationItem] = Field(default_factory=list)
    external_items: list[ReconciliationItem] = Field(default_factory=list)
    constraints: ReconciliationConstraints = Field(
        default_factory=ReconciliationConstraints
    )
    reconciliation_id: str | None = None


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
    residual_store = ResidualStore(database.session_factory)
    baseline_manager = ResidualBaselineManager(
        ResidualBaselineStore(database.session_factory)
    )
    residual_engine = ResidualIntelligenceEngine()
    distribution_analyzer = ResidualDistributionAnalyzer()
    reconciliation_service = ReconciliationService()
    finance_controller = FinanceController(repository)

    app = FastAPI(
        title="Financial Control Fabric",
        description="Deterministic canonical financial event store.",
        version="0.1.0",
    )

    def get_repository() -> FinancialEventRepository:
        return repository

    def get_registry() -> ControlRegistry:
        return registry

    def get_residual_store() -> ResidualStore:
        return residual_store

    def get_baseline_manager() -> ResidualBaselineManager:
        return baseline_manager

    def get_residual_engine() -> ResidualIntelligenceEngine:
        return residual_engine

    def get_distribution_analyzer() -> ResidualDistributionAnalyzer:
        return distribution_analyzer

    def get_reconciliation_service() -> ReconciliationService:
        return reconciliation_service

    def get_finance_controller() -> FinanceController:
        return finance_controller

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

    @app.post(
        "/reconciliation/settlement",
        response_model=ReconciliationResult,
    )
    def reconcile_settlement(
        request: ReconciliationRequest,
        service: ReconciliationService = Depends(get_reconciliation_service),
    ) -> ReconciliationResult:
        """Propose deterministic settlement allocations without side effects."""

        try:
            return service.reconcile(
                request.internal_items,
                request.external_items,
                request.constraints,
                reconciliation_id=request.reconciliation_id,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            ) from error

    @app.post("/agent/investigate", response_model=InvestigationReport)
    def investigate(
        request: InvestigationRequest,
        controller: FinanceController = Depends(get_finance_controller),
    ) -> InvestigationReport:
        """Investigate a control result through bounded read-only tools."""

        try:
            return controller.investigate(request)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            ) from error

    @app.get(
        "/agent/investigations/{investigation_id}",
        response_model=InvestigationReport,
    )
    def get_investigation(
        investigation_id: str,
        controller: FinanceController = Depends(get_finance_controller),
    ) -> InvestigationReport:
        """Retrieve one bounded investigation report."""

        record = controller.get_record(investigation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="investigation not found")
        return record.report

    @app.get(
        "/agent/investigations/{investigation_id}/evidence",
        response_model=list[EvidenceItem],
    )
    def investigation_evidence(
        investigation_id: str,
        controller: FinanceController = Depends(get_finance_controller),
    ) -> list[EvidenceItem]:
        record = controller.get_record(investigation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="investigation not found")
        return record.evidence

    @app.get(
        "/agent/investigations/{investigation_id}/hypotheses",
        response_model=list[InvestigationHypothesis],
    )
    def investigation_hypotheses(
        investigation_id: str,
        controller: FinanceController = Depends(get_finance_controller),
    ) -> list[InvestigationHypothesis]:
        record = controller.get_record(investigation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="investigation not found")
        return record.hypotheses

    @app.get(
        "/agent/investigations/{investigation_id}/audit",
        response_model=list[AgentAuditEvent],
    )
    def investigation_audit(
        investigation_id: str,
        controller: FinanceController = Depends(get_finance_controller),
    ) -> list[AgentAuditEvent]:
        audit = controller.get_audit(investigation_id)
        if not audit:
            raise HTTPException(status_code=404, detail="investigation not found")
        return audit

    @app.post(
        "/agent/investigations/{investigation_id}/recommendation",
        response_model=ControllerAction,
    )
    def investigation_recommendation(
        investigation_id: str,
        controller: FinanceController = Depends(get_finance_controller),
    ) -> ControllerAction:
        try:
            return controller.request_recommendation(investigation_id)
        except ValueError as error:
            raise HTTPException(
                status_code=404 if "not found" in str(error) else 400,
                detail=str(error),
            ) from error

    @app.post(
        "/agent/investigations/{investigation_id}/approve",
        response_model=ControllerAction,
    )
    def approve_investigation(
        investigation_id: str,
        request: ApprovalRequest,
        controller: FinanceController = Depends(get_finance_controller),
    ) -> ControllerAction:
        try:
            return controller.approve(
                investigation_id,
                approved=request.approved,
                approved_by=request.approved_by,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=404 if "not found" in str(error) else 400,
                detail=str(error),
            ) from error

    @app.post(
        "/agent/investigations/{investigation_id}/revalidate",
        response_model=RevalidationResult,
    )
    def revalidate_investigation(
        investigation_id: str,
        request: RevalidationRequest,
        controller: FinanceController = Depends(get_finance_controller),
        control_registry: ControlRegistry = Depends(get_registry),
    ) -> RevalidationResult:
        record = controller.get_record(investigation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="investigation not found")
        new_result = request.new_control_result
        if new_result is None:
            if request.events is None or request.context is None:
                raise HTTPException(
                    status_code=400,
                    detail="provide new_control_result or events and context",
                )
            try:
                context_model = CONTEXT_MODELS[record.request.domain]
                context = context_model.model_validate(request.context)
                new_result = control_registry.evaluate(
                    record.request.domain,
                    request.events,
                    context,
                )
            except (KeyError, ValueError, ValidationError) as error:
                detail = error.errors() if isinstance(error, ValidationError) else str(error)
                raise HTTPException(status_code=400, detail=detail) from error
        try:
            return controller.revalidate(investigation_id, new_result)
        except ValueError as error:
            raise HTTPException(
                status_code=404 if "not found" in str(error) else 400,
                detail=str(error),
            ) from error

    @app.get(
        "/reconciliation/{reconciliation_id}",
        response_model=ReconciliationResult,
    )
    def get_reconciliation(
        reconciliation_id: str,
        service: ReconciliationService = Depends(get_reconciliation_service),
    ) -> ReconciliationResult:
        """Retrieve a previously proposed reconciliation result."""

        result = service.get_reconciliation(reconciliation_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"reconciliation '{reconciliation_id}' not found",
            )
        return result

    @app.get("/residuals", response_model=list[ResidualObservation])
    def list_residuals(
        domain: str | None = Query(default=None),
        entity_id: str | None = Query(default=None),
        account_id: str | None = Query(default=None),
        merchant_id: str | None = Query(default=None),
        partner_id: str | None = Query(default=None),
        currency: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
        store: ResidualStore = Depends(get_residual_store),
    ) -> list[ResidualObservation]:
        """List persisted residual observations without modifying them."""

        try:
            normalized_domain = ControlDomain(domain.upper()) if domain else None
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"unknown control domain '{domain}'",
            ) from error
        return store.list_residuals(
            domain=normalized_domain,
            entity_id=entity_id,
            account_id=account_id,
            merchant_id=merchant_id,
            partner_id=partner_id,
            currency=currency,
            limit=limit,
            offset=offset,
        )

    @app.get("/residuals/distribution/{domain}", response_model=ResidualDistributionResponse)
    def residual_distribution(
        domain: str,
        currency: str | None = Query(default=None),
        entity_id: str | None = Query(default=None),
        account_id: str | None = Query(default=None),
        store: ResidualStore = Depends(get_residual_store),
        analyzer: ResidualDistributionAnalyzer = Depends(get_distribution_analyzer),
    ) -> ResidualDistributionResponse:
        """Return residual population statistics for one domain."""

        try:
            normalized_domain = ControlDomain(domain.upper())
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"control domain '{domain}' not found",
            ) from error
        observations = store.list_residuals(
            domain=normalized_domain,
            currency=currency,
            entity_id=entity_id,
            account_id=account_id,
        )
        try:
            ensure_single_currency(observations, currency)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            ) from error
        return ResidualDistributionResponse(
            domain=normalized_domain,
            statistics=analyzer.analyze(observations),
        )

    @app.get("/residuals/baseline/{domain}", response_model=ResidualBaseline)
    def get_residual_baseline(
        domain: str,
        entity_id: str | None = Query(default=None),
        account_id: str | None = Query(default=None),
        currency: str | None = Query(default=None),
        manager: ResidualBaselineManager = Depends(get_baseline_manager),
    ) -> ResidualBaseline:
        """Return the latest persisted baseline for one domain and scope."""

        try:
            normalized_domain = ControlDomain(domain.upper())
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"control domain '{domain}' not found",
            ) from error
        baseline = manager.get_latest_baseline(
            normalized_domain,
            entity_id=entity_id,
            account_id=account_id,
            currency=currency,
        )
        if baseline is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"no baseline found for domain '{domain}'",
            )
        return baseline

    @app.get("/residuals/{residual_id}", response_model=ResidualObservation)
    def get_residual(
        residual_id: str,
        store: ResidualStore = Depends(get_residual_store),
    ) -> ResidualObservation:
        """Retrieve one persisted residual observation."""

        residual = store.get_residual(residual_id)
        if residual is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"residual '{residual_id}' not found",
            )
        return residual

    @app.post("/residuals/analyze/{domain}", response_model=ResidualAnalysis)
    def analyze_residuals(
        domain: str,
        request: ResidualAnalysisRequest,
        store: ResidualStore = Depends(get_residual_store),
        manager: ResidualBaselineManager = Depends(get_baseline_manager),
        engine: ResidualIntelligenceEngine = Depends(get_residual_engine),
    ) -> ResidualAnalysis:
        """Analyze residual behavior without recording or changing observations."""

        try:
            normalized_domain = ControlDomain(domain.upper())
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"control domain '{domain}' not found",
            ) from error

        current = (
            request.residuals
            if request.residuals is not None
            else store.list_residuals_by_domain(normalized_domain)
        )
        baseline = None
        baseline_residuals = request.baseline_residuals
        if request.baseline_id:
            baseline = manager.get_baseline(request.baseline_id)
            if baseline is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"baseline '{request.baseline_id}' not found",
                )
            if baseline.domain is not normalized_domain:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="baseline domain does not match analysis domain",
                )

        try:
            return engine.analyze(
                current,
                baseline=baseline,
                baseline_residuals=baseline_residuals,
                rolling_window=request.rolling_window,
                currency=request.currency,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            ) from error

    return app

app = create_app()

__all__ = [
    "app",
    "create_app",
    "EventCreateResponse",
    "FinancialEvent",
    "ReconciliationRequest",
    "InvestigationRequest",
]