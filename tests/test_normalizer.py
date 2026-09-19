"""
Unit tests for the event normalization engine.
"""

import uuid
import pytest

from backend.events.enums import EntityType, EventType, Severity, SourceSystem
from backend.events.normalizer import EventNormalizer


@pytest.fixture
def normalizer():
    return EventNormalizer()


def test_normalize_user_prompt_example(normalizer):
    """
    Test normalization of the exact prompt example:
    {
      "source": "deadline",
      "event_type": "RENDER_JOB_FAILED",
      "project": "Project_A",
      "sequence": "SQ020",
      "shot": "SH010",
      "job_id": "job_123",
      "node_id": "render-node-42",
      "error_code": "GPU_OUT_OF_MEMORY"
    }
    """
    raw_payload = {
        "source": "deadline",
        "event_type": "RENDER_JOB_FAILED",
        "project": "Project_A",
        "sequence": "SQ020",
        "shot": "SH010",
        "job_id": "job_123",
        "node_id": "render-node-42",
        "error_code": "GPU_OUT_OF_MEMORY",
    }

    event = normalizer.normalize(raw_payload)

    # Validate IDs
    uuid.UUID(event.event_id)
    uuid.UUID(event.correlation_id)
    assert event.idempotency_key == "deadline:RENDER_JOB_FAILED:job_123:GPU_OUT_OF_MEMORY"

    # Validate Enums
    assert event.source == SourceSystem.DEADLINE
    assert event.event_type == EventType.RENDER_JOB_FAILED
    assert event.severity == Severity.HIGH

    # Validate Context & Entity
    assert event.project == "Project_A"
    assert event.sequence == "SQ020"
    assert event.shot == "SH010"
    assert event.entity.entity_type == EntityType.JOB
    assert event.entity.entity_id == "job_123"
    assert event.entity.node_id == "render-node-42"

    # Validate Error Details
    assert event.error_details is not None
    assert event.error_details.error_code == "GPU_OUT_OF_MEMORY"

    # Validate Hash
    assert len(event.raw_payload_hash) == 64


def test_normalize_node_unhealthy(normalizer):
    raw = {
        "source": "tractor",
        "event_type": "NODE_UNHEALTHY",
        "node_id": "blade-042",
        "error_code": "GPU_THERMAL_ALERT",
        "message": "Thermal shutdown threshold reached",
    }
    event = normalizer.normalize(raw)
    assert event.event_type == EventType.NODE_UNHEALTHY
    assert event.severity == Severity.CRITICAL
    assert event.entity.entity_type == EntityType.NODE
    assert event.entity.entity_id == "blade-042"


def test_normalize_asset_validation_failed(normalizer):
    raw = {
        "source": "asset_storage",
        "event_type": "ASSET_VALIDATION_FAILED",
        "project": "Project_A",
        "shot": "SH010",
        "asset_name": "/prod/assets/char/hero.usd",
        "error_code": "ROOT_LAYER_CORRUPT",
    }
    event = normalizer.normalize(raw)
    assert event.event_type == EventType.ASSET_VALIDATION_FAILED
    assert event.severity == Severity.HIGH
    assert event.entity.entity_type == EntityType.ASSET
    assert event.entity.entity_id == "/prod/assets/char/hero.usd"


def test_normalize_frame_corruption(normalizer):
    raw = {
        "source": "opencue",
        "event_type": "FRAME_CORRUPTION_DETECTED",
        "project": "Project_A",
        "shot": "SH010",
        "frame": 1042,
        "error_code": "NAN_PIXELS",
    }
    event = normalizer.normalize(raw)
    assert event.event_type == EventType.FRAME_CORRUPTION_DETECTED
    assert event.severity == Severity.HIGH
    assert event.entity.entity_type == EntityType.FRAME
    assert event.entity.entity_id == "SH010:1042"


def test_normalize_render_job_lifecycle(normalizer):
    start_raw = {
        "source": "deadline",
        "event_type": "RENDER_JOB_STARTED",
        "job_id": "job_555",
        "node_id": "blade-01",
    }
    start_event = normalizer.normalize(start_raw)
    assert start_event.event_type == EventType.RENDER_JOB_STARTED
    assert start_event.severity == Severity.LOW

    done_raw = {
        "source": "deadline",
        "event_type": "RENDER_JOB_COMPLETED",
        "job_id": "job_555",
        "node_id": "blade-01",
    }
    done_event = normalizer.normalize(done_raw)
    assert done_event.event_type == EventType.RENDER_JOB_COMPLETED
    assert done_event.severity == Severity.INFO
