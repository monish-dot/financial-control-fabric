"""Provider abstraction with a reproducible no-key implementation."""

from typing import Protocol

from backend.agent.models import InvestigationRequest


class LLMProvider(Protocol):
    """Optional language provider; it cannot execute tools or calculations."""

    def generate_hypotheses(self, request: InvestigationRequest) -> list[str]:
        ...

    def summarize_evidence(self, evidence: list[object]) -> str:
        ...

    def generate_explanation(self, facts: list[str]) -> str:
        ...


class DeterministicMockProvider:
    """Stable provider used by default and in tests without external credentials."""

    def generate_hypotheses(self, request: InvestigationRequest) -> list[str]:
        return []

    def summarize_evidence(self, evidence: list[object]) -> str:
        return f"{len(evidence)} bounded evidence item(s) collected."

    def generate_explanation(self, facts: list[str]) -> str:
        return " ".join(facts)


MockLLMProvider = DeterministicMockProvider