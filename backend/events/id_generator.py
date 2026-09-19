"""
Event ID and Idempotency key generation utilities.
"""

import hashlib
import json
import uuid
from typing import Any, Optional


def generate_event_id() -> str:
    """Generate a random UUIDv4 string for an event."""
    return str(uuid.uuid4())


def generate_correlation_id() -> str:
    """Generate a random UUIDv4 string for a correlation chain."""
    return str(uuid.uuid4())


def compute_payload_hash(payload: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 hash of a dictionary payload."""
    try:
        serialized = json.dumps(payload, sort_keys=True, default=str)
    except Exception:
        serialized = str(sorted(payload.items()))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def compute_idempotency_key(
    source: str,
    event_type: str,
    entity_id: Optional[str] = None,
    error_code: Optional[str] = None,
    explicit_key: Optional[str] = None,
) -> str:
    """
    Generate or return the idempotency key.
    If an explicit key was supplied by the upstream system, use it.
    Otherwise, construct a composite key based on source, event_type, entity_id, and error_code.
    """
    if explicit_key and explicit_key.strip():
        return explicit_key.strip()

    components = [str(source).lower(), str(event_type).upper()]
    if entity_id:
        components.append(str(entity_id))
    if error_code:
        components.append(str(error_code))

    return ":".join(components)
