"""
Unit tests for the VFX Incident Simulation generator.
"""

import pytest

from backend.events.normalizer import EventNormalizer
from simulations.event_generator import (
    create_asset_validation_event,
    create_frame_corruption_event,
    create_node_unhealthy_event,
    create_render_completed_event,
    create_render_oom_event,
    create_render_started_event,
    generate_scenario,
)


@pytest.fixture
def normalizer():
    return EventNormalizer()


def test_generator_scenarios_normalize_cleanly(normalizer):
    scenarios = ["oom", "node_failure", "asset_missing", "bad_frame", "render_lifecycle", "cascading_outage"]

    for sc in scenarios:
        events = generate_scenario(sc)
        assert len(events) >= 1
        for raw in events:
            canonical = normalizer.normalize(raw)
            assert canonical.event_id is not None
            assert canonical.source is not None
            assert canonical.event_type is not None
            assert canonical.severity is not None


def test_generator_helpers(normalizer):
    oom = create_render_oom_event(project="TestProj", shot="SH001")
    c_oom = normalizer.normalize(oom)
    assert c_oom.project == "TestProj"
    assert c_oom.shot == "SH001"
    assert c_oom.error_details.error_code == "GPU_OUT_OF_MEMORY"

    node = create_node_unhealthy_event(node_id="render-node-99")
    c_node = normalizer.normalize(node)
    assert c_node.entity.node_id == "render-node-99"

    asset = create_asset_validation_event(asset_path="/prod/tex/spec.exr")
    c_asset = normalizer.normalize(asset)
    assert c_asset.entity.asset_name == "/prod/tex/spec.exr"

    frame = create_frame_corruption_event(frame=1050)
    c_frame = normalizer.normalize(frame)
    assert c_frame.entity.frame == 1050
