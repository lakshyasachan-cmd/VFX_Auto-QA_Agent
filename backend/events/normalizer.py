"""
Event normalization logic converting raw studio payloads into CanonicalEvent models.
"""

from typing import Any
from backend.events.enums import EntityType, EventType, Severity
from backend.events.id_generator import (
    compute_idempotency_key,
    compute_payload_hash,
    generate_correlation_id,
    generate_event_id,
)
from backend.events.schemas import CanonicalEvent, ErrorDetails, RawEventPayload, VFXEntity
from backend.events.timestamps import now_utc, parse_timestamp
from backend.events.validator import validate_event_payload


def infer_severity(
    event_type: EventType,
    error_code: str | None = None,
    explicit_severity: str | None = None,
) -> Severity:
    """
    Infer canonical Severity based on explicit input, event type, and error code.
    """
    if explicit_severity:
        clean = explicit_severity.strip().upper()
        if clean in Severity.__members__:
            return Severity[clean]

    code = (error_code or "").upper()

    if event_type == EventType.NODE_UNHEALTHY:
        if any(term in code for term in ["HARDWARE", "THERMAL", "PCIE", "DEAD", "OFFLINE", "POWER"]):
            return Severity.CRITICAL
        return Severity.HIGH

    elif event_type == EventType.RENDER_JOB_FAILED:
        if any(term in code for term in ["OOM", "OUT_OF_MEMORY", "CRASH", "SEGFAULT", "SIGSEGV"]):
            return Severity.HIGH
        return Severity.MEDIUM

    elif event_type == EventType.ASSET_VALIDATION_FAILED:
        if any(term in code for term in ["MISSING", "ROOT", "STAGE_CORRUPT"]):
            return Severity.HIGH
        return Severity.MEDIUM

    elif event_type == EventType.FRAME_CORRUPTION_DETECTED:
        return Severity.HIGH

    elif event_type == EventType.RENDER_JOB_STARTED:
        return Severity.LOW

    elif event_type == EventType.RENDER_JOB_COMPLETED:
        return Severity.INFO

    return Severity.MEDIUM


def build_vfx_entity(payload: RawEventPayload, event_type: EventType) -> VFXEntity:
    """
    Construct the canonical VFXEntity and assign primary entity_type and entity_id.
    """
    asset_ref = payload.asset_name or payload.asset_path

    if event_type == EventType.NODE_UNHEALTHY and payload.node_id:
        e_type = EntityType.NODE
        e_id = payload.node_id
    elif event_type == EventType.ASSET_VALIDATION_FAILED and asset_ref:
        e_type = EntityType.ASSET
        e_id = asset_ref
    elif event_type == EventType.FRAME_CORRUPTION_DETECTED and payload.frame is not None:
        e_type = EntityType.FRAME
        prefix = payload.shot or payload.job_id or "frame"
        e_id = f"{prefix}:{payload.frame}"
    elif payload.job_id:
        e_type = EntityType.JOB
        e_id = payload.job_id
    elif payload.shot:
        e_type = EntityType.SHOT
        e_id = payload.shot
    elif payload.node_id:
        e_type = EntityType.NODE
        e_id = payload.node_id
    elif asset_ref:
        e_type = EntityType.ASSET
        e_id = asset_ref
    elif payload.sequence:
        e_type = EntityType.SEQUENCE
        e_id = payload.sequence
    else:
        e_type = EntityType.PROJECT
        e_id = payload.project or "unknown_project"

    return VFXEntity(
        entity_type=e_type,
        entity_id=e_id,
        project=payload.project,
        sequence=payload.sequence,
        shot=payload.shot,
        job_id=payload.job_id,
        node_id=payload.node_id,
        asset_name=asset_ref,
        frame=payload.frame,
    )


def build_error_details(payload: RawEventPayload, event_type: EventType) -> ErrorDetails | None:
    """
    Extract and structure error information if present or required.
    """
    if not payload.error_code and not payload.message and payload.exit_code is None:
        if event_type in (
            EventType.RENDER_JOB_FAILED,
            EventType.NODE_UNHEALTHY,
            EventType.ASSET_VALIDATION_FAILED,
            EventType.FRAME_CORRUPTION_DETECTED,
        ):
            return ErrorDetails(
                error_code="UNSPECIFIED_FAILURE",
                message=f"Event {event_type.value} occurred without explicit error message",
                exit_code=payload.exit_code,
                details=payload.metadata,
            )
        return None

    return ErrorDetails(
        error_code=payload.error_code,
        message=payload.message,
        exit_code=payload.exit_code,
        details=payload.metadata,
    )


class EventNormalizer:
    """
    Normalizes incoming raw event payloads into canonical VFX events.
    Thread-safe and stateless.
    """

    def normalize(self, raw_payload: RawEventPayload | dict[str, Any]) -> CanonicalEvent:
        """
        Validate and normalize a raw payload into CanonicalEvent.
        """
        if isinstance(raw_payload, dict):
            payload = RawEventPayload(**raw_payload)
        else:
            payload = raw_payload

        # 1. Validate source and event type
        source, event_type = validate_event_payload(payload)

        # 2. Extract and sanitize timestamps
        event_timestamp = parse_timestamp(payload.timestamp)
        ingestion_time = now_utc()

        # 3. Infer or parse severity
        severity = infer_severity(
            event_type=event_type,
            error_code=payload.error_code,
            explicit_severity=payload.severity,
        )

        # 4. Build canonical entity
        entity = build_vfx_entity(payload, event_type)

        # 5. Extract structured error details
        error_details = build_error_details(payload, event_type)

        # 6. Generate IDs
        event_id = generate_event_id()
        correlation_id = payload.correlation_id or generate_correlation_id()
        idempotency_key = compute_idempotency_key(
            source=source.value,
            event_type=event_type.value,
            entity_id=entity.entity_id,
            error_code=payload.error_code,
            explicit_key=payload.idempotency_key,
        )

        # 7. Compute raw payload hash
        raw_dict = payload.model_dump()
        payload_hash = compute_payload_hash(raw_dict)

        return CanonicalEvent(
            event_id=event_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            source=source,
            event_type=event_type,
            severity=severity,
            timestamp=event_timestamp,
            ingested_at=ingestion_time,
            project=payload.project,
            sequence=payload.sequence,
            shot=payload.shot,
            entity=entity,
            error_details=error_details,
            metrics=payload.metrics or {},
            metadata=payload.metadata or {},
            raw_payload_hash=payload_hash,
        )
