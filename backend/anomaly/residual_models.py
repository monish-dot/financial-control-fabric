"""Models for residual observations and residual intelligence outputs."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.controls.models import ControlDomain, ControlStatus


class ResidualVector(BaseModel):
    """Extensible dimensions for a residual observation."""

    model_config = ConfigDict(extra="forbid")

    amount_difference: Decimal
    timing_difference: Decimal | None = None
    fee_difference: Decimal | None = None
    tax_difference: Decimal | None = None
    quantity_difference: Decimal | None = None
    currency_difference: Decimal | None = None


class ResidualObservation(BaseModel):
    """A structured, persisted observation produced by a financial control."""

    model_config = ConfigDict(extra="forbid")

    residual_id: str = Field(min_length=1)
    control_id: str = Field(min_length=1)
    domain: ControlDomain
    entity_id: str | None = None
    account_id: str | None = None
    merchant_id: str | None = None
    partner_id: str | None = None
    timestamp: datetime
    expected_amount: Decimal
    actual_amount: Decimal
    residual_amount: Decimal
    currency: str = Field(min_length=3, max_length=3)
    status: ControlStatus
    metadata: dict[str, Any] = Field(default_factory=dict)
    vector: ResidualVector | None = None

    @field_validator("currency")
    @classmethod
    def currency_must_be_uppercase(cls, value: str) -> str:
        if not value.isalpha() or not value.isupper():
            raise ValueError("currency must be a three-letter uppercase code")
        return value

    @model_validator(mode="after")
    def residual_must_be_deterministic(self) -> "ResidualObservation":
        if self.residual_amount != self.actual_amount - self.expected_amount:
            raise ValueError("residual_amount must equal actual_amount - expected_amount")
        return self

    @classmethod
    def from_control_result(
        cls,
        result: Any,
        *,
        residual_id: str,
        timestamp: datetime,
        account_id: str | None = None,
        merchant_id: str | None = None,
        partner_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ResidualObservation":
        """Convert a control result into a structured residual observation."""

        return cls(
            residual_id=residual_id,
            control_id=result.control_id,
            domain=result.domain,
            entity_id=result.entity_id,
            account_id=account_id,
            merchant_id=merchant_id,
            partner_id=partner_id,
            timestamp=timestamp,
            expected_amount=result.expected_amount,
            actual_amount=result.actual_amount,
            residual_amount=result.residual_amount,
            currency=result.currency,
            status=result.status,
            metadata=metadata or {},
            vector=ResidualVector(amount_difference=result.residual_amount),
        )


class ResidualDistributionStatistics(BaseModel):
    """Population statistics calculated from residual amounts."""

    count: int = Field(ge=0)
    zero_residual_ratio: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    mean: Decimal
    median: Decimal
    standard_deviation: Decimal = Field(ge=Decimal("0"))
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    p95: Decimal
    p99: Decimal
    absolute_mean: Decimal = Field(ge=Decimal("0"))
    absolute_median: Decimal = Field(ge=Decimal("0"))
    positive_ratio: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    negative_ratio: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))


class DistributionShiftMetrics(BaseModel):
    """Distribution comparison metrics; values are dimensionless or amount distances."""

    baseline_count: int = Field(ge=0)
    current_count: int = Field(ge=0)
    ks_statistic: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    wasserstein_distance: Decimal = Field(ge=Decimal("0"))
    population_stability_index: Decimal = Field(ge=Decimal("0"))


class TemporalMetrics(BaseModel):
    """Rolling residual metrics and sequential change detection output."""

    rolling_window: int = Field(ge=1)
    rolling_mean: list[Decimal] = Field(default_factory=list)
    rolling_absolute_mean: list[Decimal] = Field(default_factory=list)
    rolling_zero_residual_ratio: list[Decimal] = Field(default_factory=list)
    cusum_positive: Decimal = Decimal("0")
    cusum_negative: Decimal = Decimal("0")
    cusum_max_absolute: Decimal = Decimal("0")
    cusum_change_detected: bool = False


class AnomalySeverity(StrEnum):
    """Explainable residual anomaly severity."""

    NORMAL = "NORMAL"
    WATCH = "WATCH"
    ANOMALOUS = "ANOMALOUS"
    CRITICAL = "CRITICAL"


class ResidualAnomalyScore(BaseModel):
    """Explainable score assembled from multiple analytical signals."""

    score: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    severity: AnomalySeverity
    signals: list[str] = Field(default_factory=list)
    distribution_metrics: DistributionShiftMetrics
    temporal_metrics: TemporalMetrics
    explanation: str = Field(min_length=1)


class ResidualBaseline(BaseModel):
    """A persisted normal residual population for a scope and time window."""

    baseline_id: str = Field(min_length=1)
    domain: ControlDomain
    entity_id: str | None = None
    account_id: str | None = None
    currency: str = Field(min_length=3, max_length=3)
    window_start: datetime
    window_end: datetime
    sample_count: int = Field(ge=0)
    statistics: ResidualDistributionStatistics
    created_at: datetime
    sample_residuals: list[Decimal] = Field(default_factory=list)

    @field_validator("currency")
    @classmethod
    def currency_must_be_uppercase(cls, value: str) -> str:
        if not value.isalpha() or not value.isupper():
            raise ValueError("currency must be a three-letter uppercase code")
        return value

    @model_validator(mode="after")
    def window_must_be_ordered(self) -> "ResidualBaseline":
        if self.window_end < self.window_start:
            raise ValueError("window_end must be on or after window_start")
        return self


class ResidualAnalysis(BaseModel):
    """Combined distribution, drift, and anomaly analysis output."""

    distribution_statistics: ResidualDistributionStatistics
    distribution_shift: DistributionShiftMetrics
    temporal_metrics: TemporalMetrics
    anomaly_score: ResidualAnomalyScore