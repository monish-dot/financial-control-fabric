"""Deterministic domain-specific hypothesis candidates."""

from backend.agent.llm import LLMProvider
from backend.agent.models import (
    HypothesisStatus,
    InvestigationHypothesis,
    InvestigationRequest,
    ReasoningStatus,
    RetrievalStatus,
)


HYPOTHESES_BY_DOMAIN = {
    "NODAL_ESCROW": (
        "missing bank credit",
        "missing payout",
        "duplicate payout",
        "late refund",
        "incorrect adjustment",
        "bank posting delay",
        "ingestion gap",
    ),
    "MERCHANT_PAYOUT": (
        "missing payout",
        "incorrect fee",
        "incorrect tax",
        "refund mismatch",
        "duplicate payout",
        "adjustment mismatch",
    ),
    "SETTLEMENT": (
        "partial settlement",
        "delayed settlement",
        "duplicate settlement",
        "missing partner confirmation",
        "bank posting difference",
        "fee/adjustment difference",
    ),
    "REVENUE_RECOGNITION": (
        "recognition timing difference",
        "missing recognition",
        "duplicate recognition",
        "recognition schedule mismatch",
    ),
    "CROSS_ENTITY": (
        "missing intercompany side",
        "timing mismatch",
        "amount mismatch",
        "duplicate journal",
        "configuration issue",
    ),
}


def candidate_hypotheses(
    request: InvestigationRequest,
    provider: LLMProvider | None = None,
) -> list[InvestigationHypothesis]:
    """Return a small stable set; a provider may add only named candidates."""

    descriptions = list(HYPOTHESES_BY_DOMAIN[request.domain.value])
    if provider is not None:
        for description in provider.generate_hypotheses(request):
            if description not in descriptions:
                descriptions.append(description)
    return [
        InvestigationHypothesis(
            hypothesis_id=f"{request.investigation_id}_hypothesis_{index + 1:02d}",
            description=description,
            confidence=0,
            status=HypothesisStatus.UNTESTED,
            retrieval_status=RetrievalStatus.NO_EVIDENCE,
            reasoning_status=ReasoningStatus.INCONCLUSIVE,
            explanation="Awaiting bounded evidence retrieval.",
        )
        for index, description in enumerate(descriptions)
    ]