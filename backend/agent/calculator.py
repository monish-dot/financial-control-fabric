"""Authoritative Decimal financial calculations requested by an investigator."""

from decimal import Decimal

from backend.agent.models import CalculationRequest, CalculationResult, CalculationType


class DeterministicCalculator:
    """Perform named formulas only; arbitrary expressions are not accepted."""

    def calculate(self, request: CalculationRequest) -> CalculationResult:
        values = request.model_dump(mode="json", exclude_none=True)
        if request.calculation_type is CalculationType.EXPECTED_BALANCE:
            if request.opening_balance is None:
                raise ValueError("opening_balance is required")
            result = (
                request.opening_balance
                + sum(request.credits, Decimal("0"))
                - sum(request.debits, Decimal("0"))
                + request.adjustments
            )
            formula = "opening_balance + credits - debits + adjustments"
            trace = [
                f"opening balance: {request.opening_balance}",
                f"credits total: {sum(request.credits, Decimal('0'))}",
                f"debits total: {sum(request.debits, Decimal('0'))}",
                f"adjustments: {request.adjustments}",
            ]
        elif request.calculation_type is CalculationType.MERCHANT_ENTITLEMENT:
            if request.gross_amount is None:
                raise ValueError("gross_amount is required")
            result = (
                request.gross_amount
                - request.fees
                - request.taxes
                - request.refunds
                + request.adjustments
            )
            formula = "gross - fees - taxes - refunds + adjustments"
            trace = [
                f"gross amount: {request.gross_amount}",
                f"fees: {request.fees}",
                f"taxes: {request.taxes}",
                f"refunds: {request.refunds}",
                f"adjustments: {request.adjustments}",
            ]
        elif request.calculation_type in {
            CalculationType.SETTLEMENT_TOTAL,
            CalculationType.REVENUE_TOTAL,
        }:
            result = sum(request.amounts, Decimal("0"))
            formula = "sum(amounts)"
            trace = [f"amount count: {len(request.amounts)}"]
        elif request.calculation_type is CalculationType.INTERCOMPANY_DIFFERENCE:
            if request.source_amount is None or request.destination_amount is None:
                raise ValueError("source_amount and destination_amount are required")
            result = request.source_amount - request.destination_amount
            formula = "source_amount - destination_amount"
            trace = [
                f"source amount: {request.source_amount}",
                f"destination amount: {request.destination_amount}",
            ]
        else:  # pragma: no cover - enum exhaustiveness guard
            raise ValueError(f"unsupported calculation type {request.calculation_type}")
        return CalculationResult(
            calculation_id=f"calculation_{request.calculation_type.value}",
            formula=formula,
            inputs=values,
            result=result,
            currency=request.currency,
            calculation_trace=trace + [f"result: {result}"],
        )

    def calculate_expected_balance(self, **kwargs) -> CalculationResult:
        return self.calculate(
            CalculationRequest(
                calculation_type=CalculationType.EXPECTED_BALANCE, **kwargs
            )
        )

    def calculate_merchant_entitlement(self, **kwargs) -> CalculationResult:
        return self.calculate(
            CalculationRequest(
                calculation_type=CalculationType.MERCHANT_ENTITLEMENT, **kwargs
            )
        )

    def calculate_settlement_total(self, **kwargs) -> CalculationResult:
        return self.calculate(
            CalculationRequest(
                calculation_type=CalculationType.SETTLEMENT_TOTAL, **kwargs
            )
        )

    def calculate_revenue_total(self, **kwargs) -> CalculationResult:
        return self.calculate(
            CalculationRequest(
                calculation_type=CalculationType.REVENUE_TOTAL, **kwargs
            )
        )

    def calculate_intercompany_difference(self, **kwargs) -> CalculationResult:
        return self.calculate(
            CalculationRequest(
                calculation_type=CalculationType.INTERCOMPANY_DIFFERENCE, **kwargs
            )
        )