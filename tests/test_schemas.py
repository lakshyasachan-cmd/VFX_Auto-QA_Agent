"""
Unit tests for schemas and serialization.
"""

from datetime import datetime, timezone
import uuid
import pytest

from backend.events.enums import EntityType, EventType, Severity, SourceSystem
from backend.events.schemas import (
    CanonicalEvent,
    ErrorDetails,
    RawEventPayload,
    VFXEntity,
)


def test_raw_event_payload_permissive():
    payload = RawEventPayload(
        source="deadline",
        event_type="RENDER_JOB_FAILED",
        custom_vfx_field="unregistered_metadata",
        exit_code=137,
    )
    assert payload.source == "deadline"
    assert payload.event_type == "RENDER_JOB_FAILED"
    assert payload.custom_vfx_field == "unregistered_metadata"


def test_canonical_event_serialization():
    now = datetime(2026, 9, 8, 16, 45, 0, tzinfo=timezone.utc)
    event_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    event = CanonicalEvent(
        event_id=event_id,
        correlation_id=corr_id,
        idempotency_key="deadline:job_123:RENDER_JOB_FAILED",
        source=SourceSystem.DEADLINE,
        event_type=EventType.RENDER_JOB_FAILED,
        severity=Severity.HIGH,
        timestamp=now,
        ingested_at=now,
        project="Project_A",
        sequence="SQ020",
        shot="SH010",
        entity=VFXEntity(
            entity_type=EntityType.JOB,
            entity_id="job_123",
            project="Project_A",
            sequence="SQ020",
            shot="SH010",
            job_id="job_123",
            node_id="render-node-42",
        ),
        error_details=ErrorDetails(
            error_code="GPU_OUT_OF_MEMORY",
            message="CUDA out of memory",
            exit_code=137,
        ),
        metrics={"vram_used_mb": 24576},
        metadata={"renderer": "arnold"},
        raw_payload_hash="abc123hash",
    )

    dumped = event.model_dump(mode="json")
    assert dumped["event_id"] == event_id
    assert dumped["timestamp"] == "2026-09-08T16:45:00Z"
    assert dumped["source"] == "deadline"
    assert dumped["event_type"] == "RENDER_JOB_FAILED"
    assert dumped["entity"]["entity_type"] == "job"
    assert dumped["error_details"]["error_code"] == "GPU_OUT_OF_MEMORY"
