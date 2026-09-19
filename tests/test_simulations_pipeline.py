"""
Comprehensive unit and integration tests for VFX Incident Simulation Scenarios and End-to-End Pipeline.
Validates:
1. All 8 failure scenarios generate compliant raw events.
2. Deterministic seeds produce identical event parameters.
3. Different seeds produce distinct, randomized incident payloads.
4. End-to-end execution of all 8 scenarios across the full architectural pipeline:
   simulation -> ingestion -> supervisor -> reasoning -> remediation -> policy -> MCP -> watsonx mock.
5. Audit trail and governance policy evaluation for simulation runs.
"""

import pytest
import asyncio
from typing import Any

from simulations.scenarios import (
    SCENARIO_MAP,
    get_scenario_event,
    scenario_gpu_out_of_memory,
    scenario_render_node_failure,
    scenario_corrupted_frame,
    scenario_missing_asset,
    scenario_usd_dependency_failure,
    scenario_vdb_file_failure,
    scenario_texture_version_mismatch,
    scenario_repeated_node_failure,
)
from simulations.runner import SimulationPipelineRunner


def test_all_eight_scenarios_registered():
    required_scenarios = [
        "gpu_out_of_memory",
        "render_node_failure",
        "corrupted_frame",
        "missing_asset",
        "usd_dependency_failure",
        "vdb_file_failure",
        "texture_version_mismatch",
        "repeated_node_failure",
    ]
    for sc in required_scenarios:
        assert sc in SCENARIO_MAP, f"Scenario {sc} missing from SCENARIO_MAP"
        event = get_scenario_event(sc, seed=42)
        assert isinstance(event, dict)
        assert "event_type" in event
        assert "source" in event
        assert "error_code" in event


def test_deterministic_seed_invariance():
    event_a1 = scenario_gpu_out_of_memory(seed=777)
    event_a2 = scenario_gpu_out_of_memory(seed=777)
    assert event_a1 == event_a2

    event_b1 = scenario_usd_dependency_failure(seed=999)
    event_b2 = scenario_usd_dependency_failure(seed=999)
    assert event_b1 == event_b2

    event_c1 = scenario_render_node_failure(seed=12345)
    event_c2 = scenario_render_node_failure(seed=12345)
    assert event_c1 == event_c2


def test_seed_randomization_variance():
    ev1 = scenario_gpu_out_of_memory(seed=10)
    ev2 = scenario_gpu_out_of_memory(seed=20)
    assert ev1["job_id"] != ev2["job_id"]
    assert ev1["node_id"] != ev2["node_id"]


def test_gpu_oom_event_schema():
    event = scenario_gpu_out_of_memory(seed=42)
    assert event["event_type"] == "RENDER_JOB_FAILED"
    assert event["error_code"] == "GPU_OUT_OF_MEMORY"
    assert "vram_used_mb" in event["metrics"]
    assert event["metrics"]["vram_used_mb"] > 40000


def test_render_node_failure_event_schema():
    event = scenario_render_node_failure(seed=42)
    assert event["event_type"] == "NODE_UNHEALTHY"
    assert event["error_code"] == "PCIE_BUS_DEGRADED"
    assert "gpu_temperature_c" in event["metrics"]


def test_corrupted_frame_event_schema():
    event = scenario_corrupted_frame(seed=42)
    assert event["event_type"] == "FRAME_CORRUPTION_DETECTED"
    assert "nan_pixel_percentage" in event["metrics"]
    assert event["metrics"]["nan_pixel_percentage"] > 0.0


def test_missing_asset_event_schema():
    event = scenario_missing_asset(seed=42)
    assert event["event_type"] == "ASSET_VALIDATION_FAILED"
    assert event["error_code"] == "ASSET_FILE_NOT_FOUND"
    assert "missing_file" in event["metadata"]


def test_usd_dependency_failure_event_schema():
    event = scenario_usd_dependency_failure(seed=42)
    assert event["event_type"] == "ASSET_VALIDATION_FAILED"
    assert event["error_code"] == "USD_BROKEN_REFERENCE"
    assert "unresolved_sublayer" in event["metadata"]


def test_vdb_file_failure_event_schema():
    event = scenario_vdb_file_failure(seed=42)
    assert event["event_type"] == "ASSET_VALIDATION_FAILED"
    assert event["error_code"] == "VDB_HEADER_CORRUPTED"
    assert ".vdb" in event["metadata"]["corrupt_file"]


def test_texture_version_mismatch_event_schema():
    event = scenario_texture_version_mismatch(seed=42)
    assert event["event_type"] == "ASSET_VALIDATION_FAILED"
    assert event["error_code"] == "TEXTURE_VERSION_INCOMPATIBLE"
    assert "current_version" in event["metadata"]
    assert "required_version" in event["metadata"]


def test_repeated_node_failure_event_schema():
    event = scenario_repeated_node_failure(seed=42)
    assert event["event_type"] == "NODE_UNHEALTHY"
    assert event["error_code"] == "REPEATED_NODE_FAILURE"
    assert event["metrics"]["consecutive_failures"] >= 3


@pytest.mark.asyncio
async def test_end_to_end_gpu_oom_pipeline():
    runner = SimulationPipelineRunner()
    result = await runner.run("gpu_oom", seed=101)

    assert result["success"] is True
    assert result["incident_id"].startswith("inc-")
    assert result["normalized_event"]["event_type"] == "RENDER_JOB_FAILED"
    assert result["reasoning"]["root_cause"] == "GPU_MEMORY_EXHAUSTION"
    assert len(result["approvals"]) >= 3
    assert len(result["mcp_executions"]) >= 3
    for mcp_call in result["mcp_executions"]:
        assert mcp_call["success"] is True, f"MCP execution failed: {mcp_call['error']}"


@pytest.mark.asyncio
async def test_end_to_end_missing_asset_pipeline():
    runner = SimulationPipelineRunner()
    result = await runner.run("missing_asset", seed=202)

    assert result["success"] is True
    assert result["normalized_event"]["event_type"] == "ASSET_VALIDATION_FAILED"
    assert result["remediation_plan"]["overall_risk"] in ("LOW", "MEDIUM", "HIGH")
    assert len(result["mcp_executions"]) >= 1
    for mcp_call in result["mcp_executions"]:
        assert mcp_call["success"] is True


@pytest.mark.asyncio
async def test_end_to_end_usd_dependency_pipeline():
    runner = SimulationPipelineRunner()
    result = await runner.run("usd_dependency_failure", seed=303)

    assert result["success"] is True
    assert result["reasoning"]["root_cause"] != ""
    assert len(result["timeline"]) == 8
    for mcp_call in result["mcp_executions"]:
        assert mcp_call["success"] is True


@pytest.mark.asyncio
async def test_end_to_end_repeated_node_failure_pipeline():
    runner = SimulationPipelineRunner()
    result = await runner.run("repeated_node_failure", seed=404)

    assert result["success"] is True
    assert len(result["approvals"]) >= 1
    for mcp_call in result["mcp_executions"]:
        assert mcp_call["success"] is True


@pytest.mark.asyncio
async def test_all_eight_scenarios_end_to_end():
    runner = SimulationPipelineRunner()
    scenarios = [
        "gpu_out_of_memory",
        "render_node_failure",
        "corrupted_frame",
        "missing_asset",
        "usd_dependency_failure",
        "vdb_file_failure",
        "texture_version_mismatch",
        "repeated_node_failure",
    ]
    for sc in scenarios:
        res = await runner.run(sc, seed=555)
        assert res["success"] is True
        assert len(res["timeline"]) == 8
        assert all(m["success"] is True for m in res["mcp_executions"])

