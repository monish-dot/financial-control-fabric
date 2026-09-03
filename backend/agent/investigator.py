"""Deterministic evidence-grounded investigation workflow."""

from dataclasses import dataclass
from decimal import Decimal

from backend.agent.audit import AgentAuditTrail
from backend.agent.calculator import DeterministicCalculator
from backend.agent.evidence import evidence_from_tool_result
from backend.agent.hypotheses import candidate_hypotheses
from backend.agent.llm import DeterministicMockProvider, LLMProvider
from backend.agent.models import (
    AgentState,
    AuditActor,
    ControllerAction,
    EvidenceItem,
    InvestigationHypothesis,
    InvestigationReport,
    InvestigationRequest,
    InvestigationStatus,
    Recommendation,
    RevalidationResult,
    RootCauseCategory,
    RootCauseFinding,
    RetrievalStatus,
    ReasoningStatus,
    ToolQuery,
)
from backend.agent.recommendations import recommendation_for
from backend.agent.revalidation import revalidate
from backend.agent.state_machine import InvestigationStateMachine
from backend.agent.tools import ReadOnlyFinancialTools
from backend.agent.verifier import HypothesisVerifier
from backend.controls.models import ControlResult, ControlStatus
from backend.models.financial_event import EventType, FinancialEvent
from backend.repositories.financial_event import FinancialEventRepository


@dataclass
class InvestigationRecord:
    request: InvestigationRequest
    report: InvestigationReport
    hypotheses: list[InvestigationHypothesis]
    evidence: list[EvidenceItem]
    recommendation: Recommendation
    action: ControllerAction | None
    revalidation: RevalidationResult | None
    state_machine: InvestigationStateMachine


class FinanceController:
    """Guarded controller that recommends but never executes financial actions."""

    def __init__(
        self,
        repository: FinancialEventRepository,
        *,
        provider: LLMProvider | None = None,
        calculator: DeterministicCalculator | None = None,
        audit: AgentAuditTrail | None = None,
    ) -> None:
        self._tools = ReadOnlyFinancialTools(repository)
        self._provider = provider or DeterministicMockProvider()
        self._calculator = calculator or DeterministicCalculator()
        self._verifier = HypothesisVerifier()
        self._audit = audit or AgentAuditTrail()
        self._records: dict[str, InvestigationRecord] = {}

    def investigate(self, request: InvestigationRequest) -> InvestigationReport:
        existing = self._records.get(request.investigation_id)
        if existing is not None:
            if existing.request.model_dump() != request.model_dump():
                raise ValueError("investigation_id already exists with different input")
            return existing.report

        state = InvestigationStateMachine()
        self._audit.record(
            request.investigation_id,
            timestamp=request.period_end,
            actor=AuditActor.SYSTEM,
            action="DETECTED",
            input_summary=f"control_id={request.control_id}, domain={request.domain.value}",
            output_summary="Investigation accepted for bounded analysis.",
        )
        state.transition(AgentState.INVESTIGATING)
        hypotheses = candidate_hypotheses(request, self._provider)
        self._audit.record(
            request.investigation_id,
            timestamp=request.period_end,
            actor=AuditActor.AGENT,
            action="HYPOTHESES_GENERATED",
            input_summary=f"domain={request.domain.value}",
            output_summary=f"{len(hypotheses)} deterministic candidates generated.",
        )

        events = self._retrieve_events(request)
        evidence = self._evidence(request, events)
        state.transition(AgentState.EVIDENCE_COLLECTED)
        self._audit.record(
            request.investigation_id,
            timestamp=request.period_end,
            actor=AuditActor.AGENT,
            action="EVIDENCE_COLLECTED",
            input_summary="bounded read-only event searches",
            output_summary=f"{len(events)} event(s), {len(evidence)} evidence item(s).",
            evidence_ids=[item.evidence_id for item in evidence],
        )

        calculations = self._calculate(request, events)
        self._audit.record(
            request.investigation_id,
            timestamp=request.period_end,
            actor=AuditActor.AGENT,
            action="CALCULATED",
            input_summary="named Decimal calculator functions",
            output_summary=f"{len(calculations)} calculation(s) produced.",
            evidence_ids=[item.evidence_id for item in evidence],
            calculation_ids=[item.calculation_id for item in calculations],
        )
        hypotheses, findings = self._verifier.verify(
            request,
            hypotheses,
            events,
            evidence,
            [item.calculation_id for item in calculations],
        )
        state.transition(AgentState.HYPOTHESES_TESTED)
        self._audit.record(
            request.investigation_id,
            timestamp=request.period_end,
            actor=AuditActor.AGENT,
            action="HYPOTHESES_TESTED",
            input_summary=f"{len(hypotheses)} hypotheses tested against evidence.",
            output_summary=f"{len(findings)} supported finding(s).",
            evidence_ids=[
                evidence_id
                for finding in findings
                for evidence_id in finding.supporting_evidence
            ],
            calculation_ids=[
                calculation_id
                for finding in findings
                for calculation_id in finding.calculation_ids
            ],
        )
        if not findings:
            findings = [_unknown_finding(request)]
            state.transition(AgentState.INCONCLUSIVE)
            report_status = InvestigationStatus.INCONCLUSIVE
        else:
            state.transition(AgentState.VERIFIED)
            state.transition(AgentState.RECOMMENDATION_READY)
            report_status = InvestigationStatus.COMPLETED
        recommendation = recommendation_for(findings, hypotheses)
        summary = self._summary(request, findings, recommendation)
        report = InvestigationReport(
            investigation_id=request.investigation_id,
            control_id=request.control_id,
            domain=request.domain,
            status=report_status,
            summary=summary,
            root_causes=findings,
            hypotheses=hypotheses,
            evidence=evidence,
            calculations=calculations,
            anomaly_score=request.anomaly_score,
            recommended_action=recommendation.category,
            requires_human_approval=True,
            created_at=request.period_end,
            metadata={
                "state": state.state.value,
                "financial_mutation_executed": False,
                "llm_provider": type(self._provider).__name__,
            },
        )
        self._audit.record(
            request.investigation_id,
            timestamp=request.period_end,
            actor=AuditActor.AGENT,
            action="REPORT_CREATED",
            input_summary="verified hypotheses and calculations",
            output_summary=f"status={report.status.value}, recommendation={recommendation.category.value}",
            evidence_ids=[item.evidence_id for item in evidence],
            calculation_ids=[item.calculation_id for item in calculations],
        )
        report = report.model_copy(
            update={"audit_ids": [event.audit_id for event in self._audit.list(request.investigation_id)]}
        )
        self._records[request.investigation_id] = InvestigationRecord(
            request=request,
            report=report,
            hypotheses=hypotheses,
            evidence=evidence,
            recommendation=recommendation,
            action=None,
            revalidation=None,
            state_machine=state,
        )
        return report

    def get_record(self, investigation_id: str) -> InvestigationRecord | None:
        return self._records.get(investigation_id)

    def get_audit(self, investigation_id: str):
        if investigation_id not in self._records and not self._audit.list(investigation_id):
            return []
        return self._audit.list(investigation_id)

    def request_recommendation(self, investigation_id: str) -> ControllerAction:
        record = self._get(investigation_id)
        if record.action is not None:
            return record.action
        if record.state_machine.state is not AgentState.RECOMMENDATION_READY:
            raise ValueError("recommendation is unavailable in the current investigation state")
        record.state_machine.transition(AgentState.AWAITING_APPROVAL)
        record.action = _pending_action(investigation_id, record.recommendation)
        record.report = record.report.model_copy(
            update={
                "metadata": {
                    **record.report.metadata,
                    "state": record.state_machine.state.value,
                }
            }
        )
        self._audit.record(
            investigation_id,
            timestamp=record.request.period_end,
            actor=AuditActor.AGENT,
            action="RECOMMENDATION_READY",
            input_summary="validated root-cause finding",
            output_summary=f"pending action={record.action.action_type.value}",
            evidence_ids=record.recommendation.supporting_evidence,
        )
        return record.action

    def approve(
        self,
        investigation_id: str,
        *,
        approved: bool,
        approved_by: str,
    ) -> ControllerAction:
        record = self._get(investigation_id)
        if record.action is None:
            raise ValueError("recommendation must be created before approval")
        if record.state_machine.state is not AgentState.AWAITING_APPROVAL:
            raise ValueError("approval is unavailable in the current investigation state")
        from backend.agent.approvals import record_explicit_approval

        record.action = record_explicit_approval(
            record.action,
            approved=approved,
            approved_by=approved_by,
            approved_at=record.request.period_end,
        )
        if approved:
            record.state_machine.transition(AgentState.REVALIDATING)
            record.report = record.report.model_copy(
                update={
                    "metadata": {
                        **record.report.metadata,
                        "state": record.state_machine.state.value,
                    }
                }
            )
        else:
            record.state_machine.transition(AgentState.INCONCLUSIVE)
            record.report = record.report.model_copy(
                update={
                    "metadata": {
                        **record.report.metadata,
                        "state": record.state_machine.state.value,
                    }
                }
            )
        self._audit.record(
            investigation_id,
            timestamp=record.request.period_end,
            actor=AuditActor.CONTROLLER,
            action="APPROVAL_RECORDED",
            input_summary=f"approved={approved}, approved_by={approved_by}",
            output_summary=f"approval_status={record.action.approval_status.value}; no financial mutation executed",
        )
        return record.action

    def revalidate(
        self,
        investigation_id: str,
        current_control_result: ControlResult,
    ) -> RevalidationResult:
        record = self._get(investigation_id)
        if record.state_machine.state is not AgentState.REVALIDATING:
            raise ValueError(
                "revalidation is unavailable in the current investigation state; "
                "explicit approved action is required"
            )
        result = revalidate(record.request.control_result, current_control_result)
        record.revalidation = result
        record.state_machine.transition(
            AgentState.RESOLVED if result.resolved else AgentState.INCONCLUSIVE
        )
        record.report = record.report.model_copy(
            update={
                "metadata": {
                    **record.report.metadata,
                    "state": record.state_machine.state.value,
                }
            }
        )
        self._audit.record(
            investigation_id,
            timestamp=record.request.period_end,
            actor=AuditActor.CONTROLLER,
            action="REVALIDATED",
            input_summary=f"new_status={current_control_result.status.value}",
            output_summary=f"resolved={result.resolved}",
        )
        return result

    def _retrieve_events(self, request: InvestigationRequest) -> list[FinancialEvent]:
        query = ToolQuery(
            entity_id=request.entity_id,
            account_id=request.account_id,
            merchant_id=request.merchant_id,
            partner_id=request.partner_id,
            currency=request.control_result.currency,
            period_start=request.period_start,
            period_end=request.period_end,
            limit=100,
        )
        tool_names = [
            "search_events",
            *_domain_tool_names(request.domain.value),
        ]
        collected: dict[str, FinancialEvent] = {}
        for tool_name in tool_names:
            result = getattr(self._tools, tool_name)(query)
            self._audit.record(
                request.investigation_id,
                timestamp=request.period_end,
                actor=AuditActor.AGENT,
                action="TOOL_CALLED",
                tool_name=tool_name,
                input_summary="bounded scope query",
                output_summary=f"count={result.count}, truncated={result.truncated}, retrieval={result.retrieval_status.value}",
            )
            for event in result.items:
                collected[event.event_id] = event
        return sorted(
            collected.values(),
            key=lambda event: (event.event_timestamp, event.event_id),
        )

    def _evidence(
        self,
        request: InvestigationRequest,
        events: list[FinancialEvent],
    ) -> list[EvidenceItem]:
        control_evidence = EvidenceItem(
            evidence_id=f"{request.investigation_id}_control_evidence",
            source_type="CONTROL_RESULT",
            source_id=request.control_id,
            field="residual_amount",
            value=request.control_result.residual_amount,
            timestamp=request.period_end,
            relevance=Decimal("1"),
        )
        event_evidence = [
            EvidenceItem(
                evidence_id=f"{request.investigation_id}_evidence_{index + 1:04d}",
                source_type=event.event_type.value,
                source_id=event.event_id,
                field="amount",
                value=event.amount,
                timestamp=event.event_timestamp,
                relevance=Decimal("1"),
                metadata={"currency": event.currency, "reference_id": event.source_id},
            )
            for index, event in enumerate(events)
        ]
        return [control_evidence, *event_evidence]

    def _calculate(self, request: InvestigationRequest, events: list[FinancialEvent]):
        currency = request.control_result.currency
        amounts = [event.amount for event in events]
        if not amounts:
            return []
        if request.domain.value == "MERCHANT_PAYOUT":
            result = self._calculator.calculate_merchant_entitlement(
                currency=currency,
                gross_amount=sum(
                    (event.amount for event in events if event.event_type == EventType.PAYMENT),
                    Decimal("0"),
                ),
                fees=sum(
                    (event.amount for event in events if event.event_type == EventType.FEE),
                    Decimal("0"),
                ),
                taxes=sum(
                    (event.amount for event in events if event.event_type == EventType.TAX),
                    Decimal("0"),
                ),
                refunds=sum(
                    (event.amount for event in events if event.event_type == EventType.REFUND),
                    Decimal("0"),
                ),
                adjustments=sum(
                    (event.amount for event in events if event.event_type == EventType.ADJUSTMENT),
                    Decimal("0"),
                ),
            )
        elif request.domain.value == "CROSS_ENTITY":
            result = self._calculator.calculate_intercompany_difference(
                currency=currency,
                source_amount=sum(
                    (event.amount for event in events if event.event_type == EventType.INTERCOMPANY_TRANSFER),
                    Decimal("0"),
                ),
                destination_amount=sum(
                    (event.amount for event in events if event.event_type == EventType.JOURNAL_ENTRY),
                    Decimal("0"),
                ),
            )
        elif request.domain.value == "REVENUE_RECOGNITION":
            result = self._calculator.calculate_revenue_total(
                currency=currency,
                amounts=[
                    event.amount
                    for event in events
                    if event.event_type == EventType.REVENUE_RECOGNITION
                ],
            )
        else:
            result = self._calculator.calculate_settlement_total(
                currency=currency,
                amounts=amounts,
            )
        return [
            result.model_copy(
                update={
                    "calculation_id": f"{request.investigation_id}_{result.calculation_id}"
                }
            )
        ]

    def _summary(
        self,
        request: InvestigationRequest,
        findings: list[RootCauseFinding],
        recommendation: Recommendation,
    ) -> str:
        finding = findings[0]
        return (
            f"FACT: control {request.control_id} reported residual "
            f"{request.control_result.residual_amount} {request.control_result.currency} "
            f"[{request.investigation_id}_control_evidence]. "
            f"INFERENCE: {finding.description} "
            f"ROOT CAUSE: {finding.category.value}. "
            f"UNCERTAINTY: bounded evidence and deterministic calculations only. "
            f"RECOMMENDATION: {recommendation.category.value}; human approval required."
        )

    def _get(self, investigation_id: str) -> InvestigationRecord:
        record = self._records.get(investigation_id)
        if record is None:
            raise ValueError(f"investigation '{investigation_id}' not found")
        return record


def _domain_tool_names(domain: str) -> list[str]:
    mapping = {
        "NODAL_ESCROW": [
            "search_payments",
            "search_payouts",
            "search_refunds",
            "search_adjustments",
            "search_bank_transactions",
        ],
        "MERCHANT_PAYOUT": [
            "search_payments",
            "search_payouts",
            "search_refunds",
            "search_adjustments",
            "search_events",
        ],
        "SETTLEMENT": [
            "search_settlements",
            "search_bank_transactions",
            "search_adjustments",
        ],
        "REVENUE_RECOGNITION": [
            "search_revenue_records",
            "search_payments",
            "search_events",
        ],
        "CROSS_ENTITY": [
            "search_intercompany_records",
            "search_events",
        ],
    }
    return mapping[domain]


def _unknown_finding(request: InvestigationRequest) -> RootCauseFinding:
    return RootCauseFinding(
        finding_id=f"{request.investigation_id}_finding_01",
        category=RootCauseCategory.UNKNOWN,
        description=(
            "No available transaction evidence explains the control residual; "
            "the system will not invent a cause."
        ),
        confidence=Decimal("0"),
        retrieval_status=RetrievalStatus.INSUFFICIENT_EVIDENCE,
        reasoning_status=ReasoningStatus.INCONCLUSIVE,
        impact_amount=abs(request.control_result.residual_amount),
        currency=request.control_result.currency,
    )


def _pending_action(investigation_id: str, recommendation: Recommendation) -> ControllerAction:
    from backend.agent.approvals import create_pending_action

    return create_pending_action(investigation_id, recommendation)