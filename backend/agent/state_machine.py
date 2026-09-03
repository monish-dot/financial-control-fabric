"""Explicit investigation state transitions."""

from backend.agent.models import AgentState


VALID_TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.DETECTED: {AgentState.INVESTIGATING, AgentState.INCONCLUSIVE},
    AgentState.INVESTIGATING: {
        AgentState.EVIDENCE_COLLECTED,
        AgentState.INCONCLUSIVE,
    },
    AgentState.EVIDENCE_COLLECTED: {
        AgentState.HYPOTHESES_TESTED,
        AgentState.INCONCLUSIVE,
    },
    AgentState.HYPOTHESES_TESTED: {
        AgentState.VERIFIED,
        AgentState.INCONCLUSIVE,
    },
    AgentState.VERIFIED: {AgentState.RECOMMENDATION_READY},
    AgentState.RECOMMENDATION_READY: {AgentState.AWAITING_APPROVAL},
    AgentState.AWAITING_APPROVAL: {
        AgentState.REVALIDATING,
        AgentState.INCONCLUSIVE,
    },
    AgentState.REVALIDATING: {AgentState.RESOLVED, AgentState.INCONCLUSIVE},
    AgentState.RESOLVED: set(),
    AgentState.INCONCLUSIVE: set(),
}


class InvestigationStateMachine:
    """Reject invalid controller lifecycle transitions."""

    def __init__(self, state: AgentState = AgentState.DETECTED) -> None:
        self.state = state

    def transition(self, next_state: AgentState) -> AgentState:
        if next_state not in VALID_TRANSITIONS[self.state]:
            raise ValueError(
                f"invalid investigation transition: {self.state} -> {next_state}"
            )
        self.state = next_state
        return self.state