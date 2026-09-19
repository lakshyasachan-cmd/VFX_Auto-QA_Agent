"""
VFX Event Ingestion & Normalization Subsystem.
"""

from backend.events.consumer import EventConsumer
from backend.events.dead_letter import DeadLetterHandler, DeadLetterRecord
from backend.events.enums import EntityType, EventType, Severity, SourceSystem
from backend.events.id_generator import (
    compute_idempotency_key,
    compute_payload_hash,
    generate_correlation_id,
    generate_event_id,
)
from backend.events.idempotency import (
    BaseIdempotencyStore,
    IdempotencyManager,
    MemoryIdempotencyStore,
    RedisIdempotencyStore,
)
from backend.events.normalizer import EventNormalizer
from backend.events.producer import EventProducer
from backend.events.schemas import (
    BatchIngestionRequest,
    BatchIngestionResponse,
    CanonicalEvent,
    ErrorDetails,
    IngestionResponse,
    RawEventPayload,
    VFXEntity,
)
from backend.events.service import EventIngestionService
from backend.events.timestamps import format_iso8601_utc, now_utc, parse_timestamp
from backend.events.validator import (
    EventValidationError,
    resolve_event_type,
    resolve_source_system,
    validate_event_payload,
)

__all__ = [
    "SourceSystem",
    "EventType",
    "Severity",
    "EntityType",
    "VFXEntity",
    "ErrorDetails",
    "RawEventPayload",
    "CanonicalEvent",
    "IngestionResponse",
    "BatchIngestionRequest",
    "BatchIngestionResponse",
    "generate_event_id",
    "generate_correlation_id",
    "compute_idempotency_key",
    "compute_payload_hash",
    "parse_timestamp",
    "format_iso8601_utc",
    "now_utc",
    "EventValidationError",
    "resolve_event_type",
    "resolve_source_system",
    "validate_event_payload",
    "EventNormalizer",
    "BaseIdempotencyStore",
    "MemoryIdempotencyStore",
    "RedisIdempotencyStore",
    "IdempotencyManager",
    "DeadLetterRecord",
    "DeadLetterHandler",
    "EventProducer",
    "EventConsumer",
    "EventIngestionService",
]
