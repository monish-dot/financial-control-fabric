"""Evidence-validated recommendation categories."""

from backend.agent.models import (
    InvestigationHypothesis,
    Recommendation,
    RecommendationCategory,
    RootCauseFinding,
)


def recommendation_for(
    findings: list[RootCauseFinding],
    hypotheses: list[InvestigationHypothesis],
) -> Recommendation:
    if not findings:
        return Recommendation(
            category=RecommendationCategory.INVESTIGATE_FURTHER,
            description="Retrieve additional scoped evidence before taking action.",
            supporting_evidence=[],
        )
    category_by_root_cause = {
        "MISSING_EVENT": RecommendationCategory.REVIEW_DATA_INGESTION,
        "DUPLICATE_EVENT": RecommendationCategory.REVIEW_DUPLICATE,
        "TIMING_DIFFERENCE": RecommendationCategory.WAIT_FOR_SETTLEMENT,
        "BANK_POSTING_DELAY": RecommendationCategory.WAIT_FOR_SETTLEMENT,
        "FEE_DIFFERENCE": RecommendationCategory.REVIEW_FEE,
        "TAX_DIFFERENCE": RecommendationCategory.REVIEW_TAX,
        "REVENUE_TIMING": RecommendationCategory.WAIT_FOR_SETTLEMENT,
        "INTERCOMPANY_MISMATCH": RecommendationCategory.ESCALATE_TO_CONTROLLER,
    }
    finding = findings[0]
    category = category_by_root_cause.get(
        finding.category.value, RecommendationCategory.INVESTIGATE_FURTHER
    )
    return Recommendation(
        category=category,
        description=(
            f"Review the evidence-grounded finding {finding.finding_id} "
            f"before considering any financial-impacting action."
        ),
        supporting_evidence=finding.supporting_evidence,
    )