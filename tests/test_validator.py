"""
Unit tests for event validation rules and aliases resolution.
"""

import pytest
from backend.events.enums import EventType, SourceSystem
from backend.events.schemas import RawEventPayload
from backend.events.validator import (
    EventValidationError,
    resolve_event_type,
    resolve_source_system,
    validate_event_payload,
)


def test_resolve_event_type_direct_and_aliases():
    assert resolve_event_type("RENDER_JOB_FAILED") == EventType.RENDER_JOB_FAILED
    assert resolve_event_type("job_failed") == EventType.RENDER_JOB_FAILED
    assert resolve_event_type("NODE_OFFLINE") == EventType.NODE_UNHEALTHY
    assert resolve_event_type("CORRUPT_ASSET") == EventType.ASSET_VALIDATION_FAILED
    assert resolve_event_type("FRAME_CORRUPT") == EventType.FRAME_CORRUPTION_DETECTED


def test_resolve_event_type_invalid_raises():
    with pytest.raises(EventValidationError, match="Unsupported or unknown event_type"):
        resolve_event_type("UNKNOWN_RANDOM_EVENT")


def test_resolve_source_system_aliases_and_fallback():
    assert resolve_source_system("deadline") == SourceSystem.DEADLINE
    assert resolve_source_system("thinkbox_deadline") == SourceSystem.DEADLINE
    assert resolve_source_system("tractor") == SourceSystem.TRACTOR
    assert resolve_source_system("custom_studio_bot") == SourceSystem.GENERIC_VFX


def test_validate_render_job_requires_identifier():
    payload = RawEventPayload(
        source="deadline",
        event_type="RENDER_JOB_FAILED",
        # missing job_id, shot, and node_id
    )
    with pytest.raises(EventValidationError, match="requires at least one entity identifier"):
        validate_event_payload(payload)


def test_validate_node_unhealthy_requires_node_id():
    payload = RawEventPayload(
        source="tractor",
        event_type="NODE_UNHEALTHY",
        # missing node_id
    )
    with pytest.raises(EventValidationError, match="requires a 'node_id'"):
        validate_event_payload(payload)


def test_validate_asset_validation_requires_asset_target():
    payload = RawEventPayload(
        source="asset_storage",
        event_type="ASSET_VALIDATION_FAILED",
        # missing asset_name, asset_path, shot
    )
    with pytest.raises(EventValidationError, match="requires 'asset_name', 'asset_path', or 'shot'"):
        validate_event_payload(payload)
