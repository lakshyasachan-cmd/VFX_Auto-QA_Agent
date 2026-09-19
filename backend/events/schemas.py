"""
Pydantic schemas for the VFX Event Ingestion and Normalization subsystem.
Strictly decoupled from LLMs, agents, or reasoning frameworks.
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_serializer

from backend.events.enums import EntityType, EventType, Severity, SourceSystem
from backend.events.timestamps import format_iso8601_utc


class VFXEntity(BaseModel):
    """Normalized entity descriptor representing the affected VFX asset, job, or node."""
    model_config = ConfigDict(extra="ignore")

    entity_type: EntityType = Field(description="Type of entity: job, node, asset, frame, shot, sequence, project")
    entity_id: str = Field(description="Unique identifier for the primary entity")
    project: Optional[str] = Field(default=None, description="VFX project code (e.g., Project_A)")
    sequence: Optional[str] = Field(default=None, description="Sequence identifier (e.g., SQ020)")
    shot: Optional[str] = Field(default=None, description="Shot identifier (e.g., SH010)")
    job_id: Optional[str] = Field(default=None, description="Farm job ID (e.g., job_123)")
    node_id: Optional[str] = Field(default=None, description="Worker / render blade name (e.g., render-node-42)")
    asset_name: Optional[str] = Field(default=None, description="Asset path or name (e.g., /assets/hero/hero.usd)")
    frame: Optional[int] = Field(default=None, description="Specific frame number if applicable")


class ErrorDetails(BaseModel):
    """Structured error information extracted from raw event payloads."""
    model_config = ConfigDict(extra="ignore")

    error_code: Optional[str] = Field(default=None, description="Categorical error code (e.g., GPU_OUT_OF_MEMORY)")
    message: Optional[str] = Field(default=None, description="Human-readable error or status message")
    exit_code: Optional[int] = Field(default=None, description="Process exit code from the render task")
    details: dict[str, Any] = Field(default_factory=dict, description="Arbitrary additional error context")


class RawEventPayload(BaseModel):
    """
    Schema for incoming raw webhook/API event.
    Permissive with extra fields to accommodate heterogeneous studio tools.
    """
    model_config = ConfigDict(extra="allow")

    source: str = Field(description="Source system identifier (deadline, tractor, opencue, shotgrid, etc.)")
    event_type: str = Field(description="Event classification string")
    project: Optional[str] = Field(default=None)
    sequence: Optional[str] = Field(default=None)
    shot: Optional[str] = Field(default=None)
    job_id: Optional[str] = Field(default=None)
    node_id: Optional[str] = Field(default=None)
    asset_name: Optional[str] = Field(default=None)
    asset_path: Optional[str] = Field(default=None)
    frame: Optional[int] = Field(default=None)
    error_code: Optional[str] = Field(default=None)
    message: Optional[str] = Field(default=None)
    exit_code: Optional[int] = Field(default=None)
    severity: Optional[str] = Field(default=None)
    timestamp: Optional[Any] = Field(default=None)
    idempotency_key: Optional[str] = Field(default=None)
    correlation_id: Optional[str] = Field(default=None)
    metrics: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CanonicalEvent(BaseModel):
    """
    Canonical Normalized VFX Event.
    Standard lingua franca for downstream event bus, correlation, and storage.
    """
    model_config = ConfigDict(extra="ignore", use_enum_values=True)

    event_id: str = Field(description="Unique UUIDv4 for this event occurrence")
    correlation_id: str = Field(description="Correlation UUID tracking an incident or pipeline cascade")
    idempotency_key: str = Field(description="Unique key ensuring at-most-once ingestion")
    source: SourceSystem = Field(description="Normalized source system")
    event_type: EventType = Field(description="Normalized VFX event classification")
    severity: Severity = Field(description="Assessed severity level")
    timestamp: datetime = Field(description="UTC event occurrence timestamp")
    ingested_at: datetime = Field(description="UTC timestamp when platform ingested the event")
    project: Optional[str] = Field(default=None)
    sequence: Optional[str] = Field(default=None)
    shot: Optional[str] = Field(default=None)
    entity: VFXEntity = Field(description="Affected entity details")
    error_details: Optional[ErrorDetails] = Field(default=None)
    metrics: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw_payload_hash: str = Field(description="SHA-256 hash of original incoming raw payload")

    @field_serializer("timestamp", "ingested_at")
    def serialize_datetimes(self, dt: datetime, _info: Any) -> str:
        return format_iso8601_utc(dt)


class IngestionResponse(BaseModel):
    """API response model for an ingested event."""
    model_config = ConfigDict(extra="ignore")

    status: str = Field(description="'accepted', 'duplicate_ignored', or 'failed'")
    event_id: str = Field(description="Assigned event UUID")
    correlation_id: str = Field(description="Assigned or preserved correlation UUID")
    idempotency_key: str = Field(description="Idempotency key evaluated")
    duplicate: bool = Field(default=False, description="True if this payload was previously processed")
    normalized_event: Optional[CanonicalEvent] = Field(default=None)
    message: Optional[str] = Field(default=None)


class BatchIngestionRequest(BaseModel):
    """Batch payload request."""
    events: list[RawEventPayload] = Field(..., min_length=1, max_length=1000)


class BatchIngestionResponse(BaseModel):
    """Batch payload response summary."""
    accepted_count: int
    duplicate_count: int
    failed_count: int
    results: list[IngestionResponse]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    redis_connected: bool
    database_connected: bool = True
    database_name: Optional[str] = None
    database_dialect: Optional[str] = None
    service: str = "vfx-event-ingestion"
    timestamp: str

