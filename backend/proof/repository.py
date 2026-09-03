"""Repository for persistence of cryptographic control proofs."""

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.controls.models import ControlDomain, ControlStatus
from backend.database.models import ControlProofRecord
from backend.proof.models import ControlProof


class ControlProofRepository:
    """Persist and query ControlProof records in SQLite."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def create_proof(self, proof: ControlProof) -> ControlProof:
        """Persist a ControlProof idempotently."""

        with self._session_factory() as session:
            existing = session.get(ControlProofRecord, proof.proof_id)
            if existing is not None:
                return _record_to_proof(existing)

            session.add(_proof_to_record(proof))
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                existing = session.get(ControlProofRecord, proof.proof_id)
                if existing is not None:
                    return _record_to_proof(existing)
                raise

            record = session.get(ControlProofRecord, proof.proof_id)
            return _record_to_proof(record)

    def get_proof(self, proof_id: str) -> ControlProof | None:
        """Retrieve one control proof by its unique identifier."""

        with self._session_factory() as session:
            record = session.get(ControlProofRecord, proof_id)
            return _record_to_proof(record) if record is not None else None

    def list_proofs(
        self,
        *,
        control_id: str | None = None,
        domain: ControlDomain | str | None = None,
        entity_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ControlProof]:
        """List persisted proofs with optional filtering and pagination."""

        with self._session_factory() as session:
            stmt = select(ControlProofRecord)
            if control_id is not None:
                stmt = stmt.where(ControlProofRecord.control_id == control_id)
            if domain is not None:
                domain_val = domain.value if isinstance(domain, ControlDomain) else domain
                stmt = stmt.where(ControlProofRecord.domain == domain_val)
            if entity_id is not None:
                stmt = stmt.where(ControlProofRecord.entity_id == entity_id)

            stmt = stmt.order_by(
                ControlProofRecord.generated_at.desc(),
                ControlProofRecord.proof_id,
            ).offset(offset).limit(limit)

            records = session.scalars(stmt).all()
            return [_record_to_proof(record) for record in records]


def _proof_to_record(proof: ControlProof) -> ControlProofRecord:
    return ControlProofRecord(
        proof_id=proof.proof_id,
        control_id=proof.control_id,
        domain=proof.domain.value,
        entity_id=proof.entity_id,
        period_start=proof.period_start.isoformat(),
        period_end=proof.period_end.isoformat(),
        event_count=proof.event_count,
        event_ids_json=json.dumps(proof.event_ids),
        merkle_root=proof.merkle_root,
        control_status=proof.control_status.value,
        expected_amount=format(proof.expected_amount, "f"),
        actual_amount=format(proof.actual_amount, "f"),
        residual_amount=format(proof.residual_amount, "f"),
        currency=proof.currency,
        context_json=json.dumps(proof.context, sort_keys=True, default=str),
        generated_at=proof.generated_at.isoformat(),
        metadata_json=json.dumps(proof.metadata, sort_keys=True, default=str),
    )


def _record_to_proof(record: ControlProofRecord | None) -> ControlProof:
    if record is None:
        raise ValueError("cannot convert missing control proof record")

    return ControlProof(
        proof_id=record.proof_id,
        control_id=record.control_id,
        domain=ControlDomain(record.domain),
        entity_id=record.entity_id,
        period_start=datetime.fromisoformat(record.period_start),
        period_end=datetime.fromisoformat(record.period_end),
        event_count=record.event_count,
        event_ids=json.loads(record.event_ids_json),
        merkle_root=record.merkle_root,
        control_status=ControlStatus(record.control_status),
        expected_amount=Decimal(record.expected_amount),
        actual_amount=Decimal(record.actual_amount),
        residual_amount=Decimal(record.residual_amount),
        currency=record.currency,
        context=json.loads(record.context_json),
        generated_at=datetime.fromisoformat(record.generated_at),
        metadata=json.loads(record.metadata_json),
    )
