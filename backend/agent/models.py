"""Typed contracts for the evidence-grounded Finance Controller agent."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.anomaly.residual_models import (
    ResidualAnalysis,
    ResidualDistributionStatistics,
    ResidualAnomalyScore,
)
from backend.controls.models import ControlDomain, ControlResult, ControlStatus
from backend.models.financial_event import FinancialEvent
from backend.reconciliation.models import ReconciliationResult


class RetrievalStatus(StrEnum):
    SUCCESS = "SUCCESS"
    NO_EVIDENCE = "NO_EVIDENCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ReasoningStatus(StrEnum):
    CONSISTENT = "CONSISTENT"
    INCONCLUSIVE = "INCONCLUSIVE"
    CONTRADICTED = "CONTRADICTED"


class HypothesisStatus(StrEnum):
    UNTESTED = "UNTESTED"
    SUPPORTED = "SUPPORTED"
    WEAK = "WEAK"
    REJECTED = "REJECTED"


class InvestigationStatus(StrEnum):
    INVESTIGATING = "INVESTIGATING"
    COMPLETED = "COMPLETED"
    INCONCLUSIVE = "INCONCLUSIVE"


class RecommendationCategory(StrEnum):
    INVESTIGATE_FURTHER = "INVESTIGATE_FURTHER"
    WAIT_FOR_SETTLEMENT = "WAIT_FOR_SETTLEMENT"
    REQUEST_PARTNER_CONFIRMATION = "REQUEST_PARTNER_CONFIRMATION"
    REVIEW_FEE = "REVIEW_FEE"
    REVIEW_TAX = "REVIEW_TAX"
    REVIEW_REFUND = "REVIEW_REFUND"
    REVIEW_DUPLICATE = "REVIEW_DUPLICATE"
    REVIEW_DATA_INGESTION = "REVIEW_DATA_INGESTION"
    ESCALATE_TO_CONTROLLER = "ESCALATE_TO_CONTROLLER"


class RootCauseCategory(StrEnum):
    MISSING_EVENT = "MISSING_EVENT"
    DUPLICATE_EVENT = "DUPLICATE_EVENT"
    TIMING_DIFFERENCE = "TIMING_DIFFERENCE"
    AMOUNT_DIFFERENCE = "AMOUNT_DIFFERENCE"
    FEE_DIFFERENCE = "FEE_DIFFERENCE"
    TAX_DIFFERENCE = "TAX_DIFFERENCE"
    ADJUSTMENT_DIFFERENCE = "ADJUSTMENT_DIFFERENCE"
    BANK_POSTING_DELAY = "BANK_POSTING_DELAY"
    RECONCILIATION_ALLOCATION = "RECONCILIATION_ALLOCATION"
    REVENUE_TIMING = "REVENUE_TIMING"
    INTERCOMPANY_MISMATCH = "INTERCOMPANY_MISMATCH"
    DATA_INGESTION = "DATA_INGESTION"
    UNKNOWN = "UNKNOWN"


class AgentState(StrEnum):
    DETECTED = "DETECTED"
    INVESTIGATING = "INVESTIGATING"
    EVIDENCE_COLLECTED = "EVIDENCE_COLLECTED"
    HYPOTHESES_TESTED = "HYPOTHESES_TESTED"
    VERIFIED = "VERIFIED"
    RECOMMENDATION_READY = "RECOMMENDATION_READY"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    REVALIDATING = "REVALIDATING"
    RESOLVED = "RESOLVED"
    INCONCLUSIVE = "INCONCLUSIVE"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AuditActor(StrEnum):
    SYSTEM = "SYSTEM"
    AGENT = "AGENT"
    CONTROLLER = "CONTROLLER"


class InvestigationRequest(BaseModel):
    """Serializable input to one controller investigation."""

    model_config = ConfigDict(extra="forbid")

    investigation_id: str = Field(min_length=1)
    control_id: str = Field(min_length=1)
    domain: ControlDomain
    entity_id: str | None = None
    account_id: str | None = None
    merchant_id: str | None = None
    partner_id: str | None = None
    period_start: datetime
    period_end: datetime
    control_result: ControlResult
    anomaly_score: ResidualAnomalyScore
    residual_summary: ResidualAnalysis | ResidualDistributionStatistics
    reconciliation_summary: ReconciliationResult | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolQuery(BaseModel):
    """Strict bounded query shared by the explicit read-only tools."""

    model_config = ConfigDict(extra="forbid")

    entity_id: str | None = None
    account_id: str | None = None
    merchant_id: str | None = None
    partner_id: str | None = None
    currency: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    reference_id: str | None = None
    limit: int = Field(default=100, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ToolResult(BaseModel):
    """Structured bounded result returned by a read-only tool."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    items: list[FinancialEvent] = Field(default_factory=list)
    count: int = Field(ge=0)
    truncated: bool = False
    retrieval_status: RetrievalStatus


class CalculationType(StrEnum):
    EXPECTED_BALANCE = "calculate_expected_balance"
    MERCHANT_ENTITLEMENT = "calculate_merchant_entitlement"
    SETTLEMENT_TOTAL = "calculate_settlement_total"
    REVENUE_TOTAL = "calculate_revenue_total"
    INTERCOMPANY_DIFFERENCE = "calculate_intercompany_difference"


class CalculationRequest(BaseModel):
    """Strict Decimal calculator input; no arbitrary expression evaluation."""

    model_config = ConfigDict(extra="forbid")

    calculation_type: CalculationType
    currency: str
    opening_balance: Decimal | None = None
    credits: list[Decimal] = Field(default_factory=list)
    debits: list[Decimal] = Field(default_factory=list)
    amounts: list[Decimal] = Field(default_factory=list)
    gross_amount: Decimal | None = None
    fees: Decimal = Decimal("0")
    taxes: Decimal = Decimal("0")
    refunds: Decimal = Decimal("0")
    adjustments: Decimal = Decimal("0")
    source_amount: Decimal | None = None
    destination_amount: Decimal | None = None


class CalculationResult(BaseModel):
    """Authoritative Decimal calculation output and trace."""

    model_config = ConfigDict(extra="forbid")

    calculation_id: str
    formula: str
    inputs: dict[str, Any]
    result: Decimal
    currency: str
    calculation_trace: list[str]


class EvidenceItem(BaseModel):
    """A bounded, traceable piece of retrieved evidence."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    source_type: str
    source_id: str
    field: str
    value: Any
    timestamp: datetime
    relevance: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    metadata: dict[str, Any] = Field(default_factory=dict)


class InvestigationHypothesis(BaseModel):
    """A testable explanation with explicit retrieval and reasoning outcomes."""

    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str
    description: str
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    calculation_ids: list[str] = Field(default_factory=list)
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    status: HypothesisStatus
    retrieval_status: RetrievalStatus
    reasoning_status: ReasoningStatus
    explanation: str


class RootCauseFinding(BaseModel):
    """Evidence-grounded root cause classification."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str
    category: RootCauseCategory
    description: str
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    supporting_evidence: list[str] = Field(default_factory=list)
    calculation_ids: list[str] = Field(default_factory=list)
    retrieval_status: RetrievalStatus
    reasoning_status: ReasoningStatus
    impact_amount: Decimal
    currency: str


class Recommendation(BaseModel):
    """Validated next step proposed for human review."""

    model_config = ConfigDict(extra="forbid")

    category: RecommendationCategory
    description: str
    supporting_evidence: list[str] = Field(default_factory=list)
    requires_approval: bool = True


class InvestigationReport(BaseModel):
    """Completed or inconclusive controller report."""

    model_config = ConfigDict(extra="forbid")

    investigation_id: str
    control_id: str
    domain: ControlDomain
    status: InvestigationStatus
    summary: str
    root_causes: list[RootCauseFinding] = Field(default_factory=list)
    hypotheses: list[InvestigationHypothesis] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    calculations: list[CalculationResult] = Field(default_factory=list)
    anomaly_score: ResidualAnomalyScore
    recommended_action: RecommendationCategory
    requires_human_approval: bool
    created_at: datetime
    audit_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ControllerAction(BaseModel):
    """Human approval record; financial changes are intentionally absent."""

    model_config = ConfigDict(extra="forbid")

    action_id: str
    investigation_id: str
    action_type: RecommendationCategory
    description: str
    proposed_by: AuditActor
    requires_approval: bool
    approval_status: ApprovalStatus
    approved_by: str | None = None
    approved_at: datetime | None = None

    @model_validator(mode="after")
    def agent_cannot_approve(self) -> "ControllerAction":
        if self.proposed_by is AuditActor.AGENT and (
            (self.approval_status is not ApprovalStatus.PENDING and self.approved_by is None)
            or not self.requires_approval
        ):
            raise ValueError(
                "agent-proposed financial actions must remain pending and require approval"
            )
        if not self.requires_approval:
            raise ValueError("financial-impacting controller actions require approval")
        return self


class RevalidationResult(BaseModel):
    """Comparison of the old and newly supplied control outcomes."""

    model_config = ConfigDict(extra="forbid")

    control_id: str
    previous_residual: Decimal
    new_residual: Decimal
    previous_status: ControlStatus
    new_status: ControlStatus
    resolved: bool
    explanation: str


class AgentAuditEvent(BaseModel):
    """Small audit reference, never a raw database dump."""

    model_config = ConfigDict(extra="forbid")

    audit_id: str
    investigation_id: str
    timestamp: datetime
    actor: AuditActor
    action: str
    tool_name: str | None = None
    input_summary: str
    output_summary: str
    evidence_ids: list[str] = Field(default_factory=list)
    calculation_ids: list[str] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    """Explicit human decision; the agent cannot construct this approval."""

    model_config = ConfigDict(extra="forbid")

    approved: bool
    approved_by: str = Field(min_length=1)


class RevalidationRequest(BaseModel):
    """Either a rerun control result or enough inputs to rerun it."""

    model_config = ConfigDict(extra="forbid")

    new_control_result: ControlResult | None = None
    events: list[FinancialEvent] | None = None
    context: dict[str, Any] | None = None