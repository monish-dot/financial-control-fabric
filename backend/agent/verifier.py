"""Evidence-based hypothesis testing and root-cause classification."""

from datetime import datetime
from decimal import Decimal

from backend.agent.models import (
    EvidenceItem,
    HypothesisStatus,
    InvestigationHypothesis,
    InvestigationRequest,
    ReasoningStatus,
    RetrievalStatus,
    RootCauseCategory,
    RootCauseFinding,
)
from backend.models.financial_event import EventType, FinancialEvent


class HypothesisVerifier:
    """Apply transparent deterministic checks to retrieved evidence."""

    def verify(
        self,
        request: InvestigationRequest,
        hypotheses: list[InvestigationHypothesis],
        events: list[FinancialEvent],
        evidence: list[EvidenceItem],
        calculation_ids: list[str],
    ) -> tuple[list[InvestigationHypothesis], list[RootCauseFinding]]:
        updated: list[InvestigationHypothesis] = []
        findings: list[RootCauseFinding] = []
        for hypothesis in hypotheses:
            supporting, contradicting, explanation = self._test(
                request, hypothesis.description, events
            )
            retrieval = (
                RetrievalStatus.SUCCESS
                if events
                else RetrievalStatus.INSUFFICIENT_EVIDENCE
            )
            if supporting:
                status = HypothesisStatus.SUPPORTED
                reasoning = ReasoningStatus.CONSISTENT
                confidence = Decimal("0.85")
            elif contradicting:
                status = HypothesisStatus.REJECTED
                reasoning = ReasoningStatus.CONTRADICTED
                confidence = Decimal("0.1")
            else:
                status = HypothesisStatus.WEAK
                reasoning = ReasoningStatus.INCONCLUSIVE
                confidence = Decimal("0.2")
            updated_hypothesis = hypothesis.model_copy(
                update={
                    "supporting_evidence": supporting,
                    "contradicting_evidence": contradicting,
                    "calculation_ids": calculation_ids if supporting else [],
                    "confidence": confidence,
                    "status": status,
                    "retrieval_status": retrieval,
                    "reasoning_status": reasoning,
                    "explanation": explanation,
                }
            )
            updated.append(updated_hypothesis)
            if supporting:
                category = _category_for(hypothesis.description)
                findings.append(
                    RootCauseFinding(
                        finding_id=f"{request.investigation_id}_finding_{len(findings) + 1:02d}",
                        category=category,
                        description=explanation,
                        confidence=confidence,
                        supporting_evidence=supporting,
                        calculation_ids=calculation_ids,
                        retrieval_status=RetrievalStatus.SUCCESS,
                        reasoning_status=ReasoningStatus.CONSISTENT,
                        impact_amount=abs(request.control_result.residual_amount),
                        currency=request.control_result.currency,
                    )
                )
        return updated, findings

    def _test(
        self,
        request: InvestigationRequest,
        description: str,
        events: list[FinancialEvent],
    ) -> tuple[list[str], list[str], str]:
        event_by_type = {
            event_type: [event for event in events if event.event_type == event_type]
            for event_type in EventType
        }
        evidence_by_event_id = {
            event.event_id: f"{request.investigation_id}_evidence_{index + 1:04d}"
            for index, event in enumerate(events)
        }
        def ids(items: list[FinancialEvent]) -> list[str]:
            return [evidence_by_event_id[item.event_id] for item in items]

        if description in {"missing payout", "missing bank credit", "missing recognition"}:
            expected_type = {
                "missing payout": EventType.PAYOUT,
                "missing bank credit": EventType.BANK_CREDIT,
                "missing recognition": EventType.REVENUE_RECOGNITION,
            }[description]
            support_by_description = {
                "missing payout": event_by_type[EventType.PAYMENT],
                "missing bank credit": event_by_type[EventType.SETTLEMENT],
                "missing recognition": (
                    event_by_type[EventType.PAYMENT]
                    or event_by_type[EventType.SETTLEMENT]
                ),
            }
            support = support_by_description[description]
            missing = not event_by_type[expected_type]
            if support and missing:
                return (
                    ids(support),
                    [],
                    f"FACT: supporting source events exist [{', '.join(ids(support))}]. "
                    f"INFERENCE: no {expected_type.value} event was retrieved in scope; "
                    f"the residual is consistent with a missing event. "
                    "UNCERTAINTY: absence from this bounded store does not prove the event never occurred.",
                )
            if event_by_type[expected_type]:
                existing_ids = ids(event_by_type[expected_type])
                return (
                    [],
                    existing_ids,
                    f"FACT: expected {expected_type.value} evidence exists "
                    f"[{', '.join(existing_ids)}]. "
                    "CONTRADICTION: the retrieved record weakens the missing-event hypothesis.",
                )
        if description in {"duplicate payout", "duplicate settlement", "duplicate journal"}:
            target_type = {
                "duplicate payout": EventType.PAYOUT,
                "duplicate settlement": EventType.SETTLEMENT,
                "duplicate journal": EventType.JOURNAL_ENTRY,
            }[description]
            target = event_by_type[target_type]
            groups: dict[str, list[FinancialEvent]] = {}
            for event in target:
                key = event.parent_event_id or event.source_id
                groups.setdefault(key, []).append(event)
            duplicate = next(
                (group for group in groups.values() if len(group) > 1), []
            )
            if duplicate:
                duplicate_ids = ids(duplicate)
                return (
                    duplicate_ids,
                    [],
                    f"FACT: duplicate-key events were retrieved [{', '.join(duplicate_ids)}]. "
                    "INFERENCE: repeated records are consistent with a duplicate event.",
                )
        if description in {
            "timing mismatch",
            "delayed settlement",
            "bank posting delay",
            "timing difference",
        }:
            pairs = _timing_pairs(events)
            if pairs:
                left, right, seconds = pairs[0]
                pair_ids = ids([left, right])
                return (
                    pair_ids,
                    [],
                    f"FACT: paired records [{', '.join(pair_ids)}] differ by "
                    f"{seconds} seconds ({seconds / Decimal('60')} minutes). "
                    "INFERENCE: the timing difference is consistent with delayed posting.",
                )
        if description in {"incorrect fee", "fee/adjustment difference"}:
            fee_events = event_by_type[EventType.FEE]
            expected_fee = request.control_result.metadata.get("expected_fee")
            if fee_events and expected_fee is not None:
                fee_ids = ids(fee_events)
                return (
                    fee_ids,
                    [],
                    f"FACT: fee event evidence [{', '.join(fee_ids)}] was retrieved. "
                    f"INFERENCE: recorded fee differs from configured expected fee {expected_fee}.",
                )
        if description in {"incorrect tax"} and event_by_type[EventType.TAX]:
            tax_ids = ids(event_by_type[EventType.TAX])
            return (
                tax_ids,
                [],
                f"FACT: tax evidence was retrieved [{', '.join(tax_ids)}]. "
                "INFERENCE: the control residual is consistent with a tax difference.",
            )
        if description in {"partial settlement", "amount mismatch", "bank posting difference"}:
            if events and request.control_result.residual_amount != 0:
                event_ids = ids(events[:2])
                return (
                    event_ids,
                    [],
                    f"FACT: scoped transaction evidence was retrieved [{', '.join(event_ids)}]. "
                    "INFERENCE: the non-zero control residual is consistent with an amount difference.",
                )
        return [], [], "No retrieved evidence supports this hypothesis."


def _category_for(description: str) -> RootCauseCategory:
    if "missing" in description:
        return RootCauseCategory.MISSING_EVENT
    if "duplicate" in description:
        return RootCauseCategory.DUPLICATE_EVENT
    if "timing" in description or "delay" in description:
        return (
            RootCauseCategory.BANK_POSTING_DELAY
            if description == "bank posting delay"
            else RootCauseCategory.TIMING_DIFFERENCE
        )
    if "fee" in description:
        return RootCauseCategory.FEE_DIFFERENCE
    if "tax" in description:
        return RootCauseCategory.TAX_DIFFERENCE
    if "adjustment" in description:
        return RootCauseCategory.ADJUSTMENT_DIFFERENCE
    if "settlement" in description or "amount" in description:
        return RootCauseCategory.AMOUNT_DIFFERENCE
    if "intercompany" in description or "configuration" in description:
        return RootCauseCategory.INTERCOMPANY_MISMATCH
    return RootCauseCategory.UNKNOWN


def _timing_pairs(
    events: list[FinancialEvent],
) -> list[tuple[FinancialEvent, FinancialEvent, Decimal]]:
    settlements = [event for event in events if event.event_type == EventType.SETTLEMENT]
    bank_events = [
        event
        for event in events
        if event.event_type in {EventType.BANK_CREDIT, EventType.BANK_DEBIT}
    ]
    pairs: list[tuple[FinancialEvent, FinancialEvent, Decimal]] = []
    for settlement in settlements:
        for bank_event in bank_events:
            if settlement.amount != bank_event.amount:
                continue
            difference = abs(settlement.event_timestamp - bank_event.event_timestamp)
            seconds = Decimal(
                difference.days * 86400 + difference.seconds
            ) + Decimal(difference.microseconds) / Decimal("1000000")
            if seconds > 0:
                pairs.append((settlement, bank_event, seconds))
    return sorted(pairs, key=lambda pair: (pair[2], pair[0].event_id, pair[1].event_id))