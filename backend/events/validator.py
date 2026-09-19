"""
Validation rules and domain integrity checks for incoming VFX events.
"""

from typing import Any
from backend.events.enums import EventType, SourceSystem
from backend.events.schemas import RawEventPayload


class EventValidationError(ValueError):
    """Raised when an incoming raw event fails domain validation."""

    def __init__(self, message: str, field: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.field = field
        self.details = details or {}


EVENT_TYPE_MAPPINGS = {
    # Direct matches
    "RENDER_JOB_FAILED": EventType.RENDER_JOB_FAILED,
    "RENDER_JOB_COMPLETED": EventType.RENDER_JOB_COMPLETED,
    "RENDER_JOB_STARTED": EventType.RENDER_JOB_STARTED,
    "NODE_UNHEALTHY": EventType.NODE_UNHEALTHY,
    "ASSET_VALIDATION_FAILED": EventType.ASSET_VALIDATION_FAILED,
    "FRAME_CORRUPTION_DETECTED": EventType.FRAME_CORRUPTION_DETECTED,
    # Common variations / aliases from production tools
    "JOB_FAILED": EventType.RENDER_JOB_FAILED,
    "TASK_FAILED": EventType.RENDER_JOB_FAILED,
    "RENDER_FAILED": EventType.RENDER_JOB_FAILED,
    "JOB_COMPLETED": EventType.RENDER_JOB_COMPLETED,
    "TASK_COMPLETED": EventType.RENDER_JOB_COMPLETED,
    "RENDER_FINISHED": EventType.RENDER_JOB_COMPLETED,
    "JOB_STARTED": EventType.RENDER_JOB_STARTED,
    "TASK_STARTED": EventType.RENDER_JOB_STARTED,
    "NODE_OFFLINE": EventType.NODE_UNHEALTHY,
    "NODE_DEGRADED": EventType.NODE_UNHEALTHY,
    "BLADE_ERROR": EventType.NODE_UNHEALTHY,
    "ASSET_ERROR": EventType.ASSET_VALIDATION_FAILED,
    "CORRUPT_ASSET": EventType.ASSET_VALIDATION_FAILED,
    "USD_VALIDATION_ERROR": EventType.ASSET_VALIDATION_FAILED,
    "FRAME_CORRUPT": EventType.FRAME_CORRUPTION_DETECTED,
    "CORRUPT_FRAME": EventType.FRAME_CORRUPTION_DETECTED,
    "BAD_PIXELS": EventType.FRAME_CORRUPTION_DETECTED,
}

SOURCE_SYSTEM_MAPPINGS = {
    "deadline": SourceSystem.DEADLINE,
    "thinkbox_deadline": SourceSystem.DEADLINE,
    "tractor": SourceSystem.TRACTOR,
    "pixar_tractor": SourceSystem.TRACTOR,
    "opencue": SourceSystem.OPENCUE,
    "cue": SourceSystem.OPENCUE,
    "shotgrid": SourceSystem.SHOTGRID,
    "shotgun": SourceSystem.SHOTGRID,
    "ftrack": SourceSystem.FTRACK,
    "asset_storage": SourceSystem.ASSET_STORAGE,
    "storage": SourceSystem.ASSET_STORAGE,
    "storage_monitor": SourceSystem.STORAGE_MONITOR,
}


def resolve_event_type(raw_type: str) -> EventType:
    """Resolve raw event string to canonical EventType enum."""
    if not raw_type or not raw_type.strip():
        raise EventValidationError("Field 'event_type' must not be empty", field="event_type")

    clean_type = raw_type.strip().upper().replace(" ", "_").replace("-", "_")
    if clean_type in EVENT_TYPE_MAPPINGS:
        return EVENT_TYPE_MAPPINGS[clean_type]

    valid_types = [e.value for e in EventType]
    raise EventValidationError(
        f"Unsupported or unknown event_type '{raw_type}'. Must be one of: {valid_types}",
        field="event_type",
        details={"provided": raw_type, "allowed": valid_types},
    )


def resolve_source_system(raw_source: str) -> SourceSystem:
    """Resolve raw source string to canonical SourceSystem enum."""
    if not raw_source or not raw_source.strip():
        raise EventValidationError("Field 'source' must not be empty", field="source")

    clean_source = raw_source.strip().lower()
    if clean_source in SOURCE_SYSTEM_MAPPINGS:
        return SOURCE_SYSTEM_MAPPINGS[clean_source]

    # Return generic_vfx for unrecognized studio custom tools
    return SourceSystem.GENERIC_VFX


def validate_event_payload(payload: RawEventPayload) -> tuple[SourceSystem, EventType]:
    """
    Validate raw event payload and return normalized SourceSystem and EventType.
    Enforces entity integrity rules based on event category.
    """
    source = resolve_source_system(payload.source)
    event_type = resolve_event_type(payload.event_type)

    # Domain integrity checks
    if event_type in (EventType.RENDER_JOB_FAILED, EventType.RENDER_JOB_COMPLETED, EventType.RENDER_JOB_STARTED):
        if not payload.job_id and not payload.shot and not payload.node_id:
            raise EventValidationError(
                f"Event '{event_type.value}' requires at least one entity identifier: 'job_id', 'shot', or 'node_id'",
                field="job_id",
            )

    elif event_type == EventType.NODE_UNHEALTHY:
        if not payload.node_id:
            raise EventValidationError(
                "Event 'NODE_UNHEALTHY' requires a 'node_id'",
                field="node_id",
            )

    elif event_type == EventType.ASSET_VALIDATION_FAILED:
        asset_target = payload.asset_name or payload.asset_path
        if not asset_target and not payload.shot:
            raise EventValidationError(
                "Event 'ASSET_VALIDATION_FAILED' requires 'asset_name', 'asset_path', or 'shot'",
                field="asset_name",
            )

    elif event_type == EventType.FRAME_CORRUPTION_DETECTED:
        if not payload.shot and not payload.job_id and payload.frame is None and not payload.node_id:
            raise EventValidationError(
                "Event 'FRAME_CORRUPTION_DETECTED' requires at least one of: 'frame', 'shot', 'job_id', or 'node_id'",
                field="frame",
            )

    return source, event_type
