"""Registry for selecting deterministic controls by domain."""

from collections.abc import Sequence

from backend.controls.base import FinancialControl
from backend.controls.cross_entity import CrossEntityControl
from backend.controls.merchant_payout import MerchantPayoutControl
from backend.controls.models import (
    ControlContext,
    ControlDomain,
    ControlResult,
)
from backend.controls.nodal_escrow import NodalEscrowControl
from backend.controls.revenue_recognition import RevenueRecognitionControl
from backend.controls.settlement import SettlementControl
from backend.models.financial_event import FinancialEvent


class ControlRegistry:
    """Register and retrieve one deterministic control per domain."""

    def __init__(self) -> None:
        self._controls: dict[ControlDomain, FinancialControl] = {}

    def register(self, control: FinancialControl) -> None:
        if control.domain in self._controls:
            raise ValueError(f"control already registered for {control.domain.value}")
        self._controls[control.domain] = control

    def get(self, domain: ControlDomain | str) -> FinancialControl:
        normalized = ControlDomain(domain.upper()) if isinstance(domain, str) else domain
        try:
            return self._controls[normalized]
        except KeyError as error:
            raise KeyError(f"unknown control domain: {normalized}") from error

    def domains(self) -> list[ControlDomain]:
        return list(self._controls)

    def evaluate(
        self,
        domain: ControlDomain | str,
        events: Sequence[FinancialEvent],
        context: ControlContext,
    ) -> ControlResult:
        return self.get(domain).evaluate(events, context)


def build_default_registry() -> ControlRegistry:
    """Build the five Phase 2 controls."""

    registry = ControlRegistry()
    for control in (
        NodalEscrowControl(),
        SettlementControl(),
        MerchantPayoutControl(),
        RevenueRecognitionControl(),
        CrossEntityControl(),
    ):
        registry.register(control)
    return registry