"""Deterministic canonical serialization and cryptographic hashing.

This module specifies and enforces the exact byte representation of canonical
financial events and node pairs in the binary Merkle tree.
"""

from collections.abc import Iterable
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Final

from backend.models.financial_event import FinancialEvent

EMPTY_TREE_ROOT: Final[str] = hashlib.sha256(b"").hexdigest()


def _as_utc(value: datetime) -> datetime:
    """Normalize naive or aware datetime to UTC without changing instant."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def canonical_sort_events(events: Iterable[FinancialEvent]) -> list[FinancialEvent]:
    """Deterministically order events by (event_timestamp_UTC, event_id).

    This ensures that any permutation of the same event set produces the
    identical canonical sequence and the identical Merkle root.
    """

    return sorted(
        events,
        key=lambda event: (_as_utc(event.event_timestamp), event.event_id),
    )


def canonical_event_dict(event: FinancialEvent) -> dict[str, Any]:
    """Construct a canonical dictionary with deterministic key names and formats.

    - Decimal amounts are formatted to exact fixed-point text via format(amount, 'f').
    - Timestamps are normalized to UTC ISO-8601 strings.
    - Currencies are uppercase 3-letter codes.
    - Missing optional fields are explicitly None (null in JSON).
    """

    return {
        "account_id": event.account_id,
        "amount": format(event.amount, "f"),
        "currency": event.currency,
        "effective_timestamp": _as_utc(event.effective_timestamp).isoformat(),
        "entity_id": event.entity_id,
        "event_id": event.event_id,
        "event_timestamp": _as_utc(event.event_timestamp).isoformat(),
        "event_type": event.event_type.value,
        "merchant_id": event.merchant_id,
        "metadata": event.metadata,
        "parent_event_id": event.parent_event_id,
        "partner_id": event.partner_id,
        "source_id": event.source_id,
        "source_system": event.source_system,
        "status": event.status,
    }


def canonical_event_bytes(event: FinancialEvent) -> bytes:
    """Produce deterministic UTF-8 bytes for an event via canonical JSON formatting.

    Keys are strictly sorted, separators are compact (',', ':'), and ASCII is preserved.
    """

    payload = canonical_event_dict(event)
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def canonical_event_hash(event: FinancialEvent) -> str:
    """Calculate the 64-character lowercase hexadecimal SHA-256 leaf digest."""

    return hashlib.sha256(canonical_event_bytes(event)).hexdigest()


def hash_pair(left_hex: str, right_hex: str) -> str:
    """Calculate the parent SHA-256 digest from concatenated raw binary child digests.

    Parent = SHA-256(left_digest_bytes || right_digest_bytes)
    """

    left_bytes = bytes.fromhex(left_hex)
    right_bytes = bytes.fromhex(right_hex)
    return hashlib.sha256(left_bytes + right_bytes).hexdigest()
