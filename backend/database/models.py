"""SQLAlchemy persistence models for the canonical event store."""

from sqlalchemy import Index, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for database models."""


class FinancialEventRecord(Base):
    """SQLite representation of a canonical FinancialEvent.

    Amount and timestamps are stored as text deliberately: SQLite has no
    native Decimal or timezone-aware timestamp type, and text preserves the
    exact Decimal representation and ISO-8601 timestamp value.
    """

    __tablename__ = "financial_events"
    __table_args__ = (
        Index("ix_financial_events_event_type", "event_type"),
        Index("ix_financial_events_entity_id", "entity_id"),
        Index("ix_financial_events_account_id", "account_id"),
        Index("ix_financial_events_merchant_id", "merchant_id"),
    )

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_system: Mapped[str] = mapped_column(String(255), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    merchant_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    partner_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    event_timestamp: Mapped[str] = mapped_column(Text, nullable=False)
    effective_timestamp: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[str] = mapped_column("metadata", Text, nullable=False)


class ResidualObservationRecord(Base):
    """SQLite representation of a structured residual observation."""

    __tablename__ = "residual_observations"
    __table_args__ = (
        Index("ix_residual_observations_domain", "domain"),
        Index("ix_residual_observations_entity_id", "entity_id"),
        Index("ix_residual_observations_account_id", "account_id"),
        Index("ix_residual_observations_merchant_id", "merchant_id"),
        Index("ix_residual_observations_timestamp", "timestamp"),
    )

    residual_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    control_id: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    merchant_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    partner_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)
    expected_amount: Mapped[str] = mapped_column(Text, nullable=False)
    actual_amount: Mapped[str] = mapped_column(Text, nullable=False)
    residual_amount: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    metadata_json: Mapped[str] = mapped_column("metadata", Text, nullable=False)
    vector_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class ResidualBaselineRecord(Base):
    """SQLite representation of a residual distribution baseline."""

    __tablename__ = "residual_baselines"
    __table_args__ = (
        Index("ix_residual_baselines_domain", "domain"),
        Index("ix_residual_baselines_window", "window_start", "window_end"),
    )

    baseline_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    window_start: Mapped[str] = mapped_column(Text, nullable=False)
    window_end: Mapped[str] = mapped_column(Text, nullable=False)
    sample_count: Mapped[int] = mapped_column(nullable=False)
    statistics_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    sample_residuals_json: Mapped[str] = mapped_column(Text, nullable=False)