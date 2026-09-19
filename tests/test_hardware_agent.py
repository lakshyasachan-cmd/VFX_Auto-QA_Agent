"""
Unit and integration tests for the Hardware Diagnostics Specialist Agent.
Tests verify:
1. Scenario 1: Healthy Render Blade (nominal GPU, CPU, RAM, disk, 0 failures)
2. Scenario 2: GPU Out-Of-Memory Failure (99.6% VRAM, CUDA OOM error logged)
3. Scenario 3: Overheating & Thermal Throttling (94°C temp, PCIe width degraded to x1, 14 ECC errors)
4. Scenario 4: Scratch Disk Full (99.99% capacity, ENOSPC write errors)
5. Scenario 5: Driver Crash / Unresponsive (device communication lost, Xid 61 / 999)
6. Scenario 6: Unavailable Telemetry (strict anti-hallucination, confidence 0.0, zero invented evidence)
7. Scenario 7: Repeated Node Failures Detection
8. Scenario 8: Renderer & CUDA Compatibility Analysis
9. Scenario 9: Google ADK Supervisor Contract Integration (async investigate)
10. Scenario 10: Non-Execution of Remediation Actions (strictly diagnostics only)
"""

import pytest

from backend.agents.hardware.agent import HardwareDiagnosticAgent
from backend.agents.hardware.mock_telemetry import HardwareTelemetryStore
from backend.agents.hardware.tools import (
    get_cpu_metrics,
    get_disk_metrics,
    get_driver_status,
    get_gpu_metrics,
    get_memory_metrics,
    get_node_health,
)


@pytest.fixture
def hw_agent():
    return HardwareDiagnosticAgent()


# ── Scenario 1: Healthy Render Blade ──────────────────────────────────────────

def test_scenario_1_healthy_node(hw_agent):
    """Scenario 1: Verifies nominal parameters on a healthy render blade."""
    node_id = "node-healthy"

    # 1. Direct tool tests
    health = get_node_health(node_id, store=hw_agent.store)
    assert health["available"] is True
    assert health["status"] == "HEALTHY"
    assert health["consecutive_failures"] == 0

    gpu = get_gpu_metrics(node_id, store=hw_agent.store)
    assert gpu["available"] is True
    assert gpu["memory_utilization_pct"] == 25.0
    assert gpu["temperature_c"] == 58.0
    assert gpu["pcie_link_width"] == 16
    assert gpu["ecc_errors_uncorrectable"] == 0

    cpu = get_cpu_metrics(node_id, store=hw_agent.store)
    assert cpu["available"] is True
    assert cpu["cpu_utilization_pct"] == 35.0

    mem = get_memory_metrics(node_id, store=hw_agent.store)
    assert mem["available"] is True
    assert mem["ram_utilization_pct"] == 25.0

    disk = get_disk_metrics(node_id, store=hw_agent.store)
    assert disk["available"] is True
    assert disk["disk_utilization_pct"] == 30.0
    assert disk["io_errors"] == 0

    drv = get_driver_status(node_id, store=hw_agent.store)
    assert drv["available"] is True
    assert drv["is_driver_responsive"] is True
    assert len(drv["xid_errors"]) == 0

    # 2. Full agent analysis
    report = hw_agent.analyze_node(node_id)
    assert report.telemetry_available is True
    assert report.overall_confidence >= 0.90

    healthy_finding = next(f for f in report.findings if f.finding_type == "NODE_HEALTHY")
    assert healthy_finding.severity == "INFO"
    assert any("nominal" in obs.lower() or "healthy" in obs.lower() for obs in healthy_finding.observed)
    assert any("hardware is fully operational" in inf.lower() for inf in healthy_finding.inferred)


# ── Scenario 2: GPU Out-Of-Memory Exhaustion ───────────────────────────────────

def test_scenario_2_gpu_oom(hw_agent):
    """Scenario 2: Detects 99.6% VRAM usage, CUDA OOM error, and memory exceedance."""
    node_id = "node-gpu-oom"

    gpu = get_gpu_metrics(node_id, store=hw_agent.store)
    assert gpu["available"] is True
    assert gpu["memory_utilization_pct"] >= 99.0
    assert gpu["memory_used_mb"] == 24480.0

    drv = get_driver_status(node_id, store=hw_agent.store)
    assert any("out of memory" in xid.get("message", "").lower() for xid in drv["xid_errors"])

    # Agent analysis
    report = hw_agent.analyze_node(node_id, context={"error_details": "CUDA out of memory"})
    oom_finding = next(f for f in report.findings if f.finding_type == "GPU_MEMORY_EXHAUSTION")

    assert oom_finding.confidence >= 0.95
    assert oom_finding.severity == "HIGH"
    assert any("99.6%" in ev for ev in oom_finding.evidence)
    assert any("CUDA OOM" in ev for ev in oom_finding.evidence)

    # Epistemic checks
    assert any("24480MB" in obs for obs in oom_finding.observed)
    assert any("exceeded physical vram capacity" in inf.lower() for inf in oom_finding.inferred)
    assert len(oom_finding.unknown) > 0


# ── Scenario 3: Overheating & Thermal Throttling ──────────────────────────────

def test_scenario_3_overheating(hw_agent):
    """Scenario 3: Detects 94°C junction temp, thermal throttling, PCIe x1 degradation, and ECC errors."""
    node_id = "node-overheating"

    gpu = get_gpu_metrics(node_id, store=hw_agent.store)
    assert gpu["available"] is True
    assert gpu["temperature_c"] == 94.0
    assert gpu["throttle_status"] == "SW_THERMAL_SLOWDOWN"
    assert gpu["pcie_link_width"] == 1
    assert gpu["ecc_errors_uncorrectable"] == 14

    report = hw_agent.analyze_node(node_id)
    thermal_finding = next(f for f in report.findings if f.finding_type == "OVERHEATING_AND_THERMAL_THROTTLING")

    assert thermal_finding.severity == "CRITICAL"
    assert thermal_finding.confidence >= 0.95
    assert any("94.0°C" in ev for ev in thermal_finding.evidence)
    assert any("SW_THERMAL_SLOWDOWN" in ev for ev in thermal_finding.evidence)
    assert any("PCIe link width degraded to x1" in ev for ev in thermal_finding.evidence)
    assert any("14 uncorrectable ECC" in ev for ev in thermal_finding.evidence)

    # Epistemic facts
    assert any("measured at 94.0°C" in obs for obs in thermal_finding.observed)
    assert any("cooling failure" in inf.lower() for inf in thermal_finding.inferred)
    assert any("ambient" in unk.lower() for unk in thermal_finding.unknown)


# ── Scenario 4: Scratch Disk Full ─────────────────────────────────────────────

def test_scenario_4_disk_full(hw_agent):
    """Scenario 4: Detects 99.99% disk space utilization and ENOSPC errors on /scratch."""
    node_id = "node-disk-full"

    disk = get_disk_metrics(node_id, store=hw_agent.store)
    assert disk["available"] is True
    assert disk["disk_utilization_pct"] >= 99.9
    assert disk["free_space_gb"] <= 0.5
    assert disk["io_errors"] == 12
    assert any("ENOSPC" in msg for msg in disk["error_messages"])

    report = hw_agent.analyze_node(node_id)
    disk_finding = next(f for f in report.findings if f.finding_type == "DISK_SPACE_EXHAUSTION")

    assert disk_finding.severity == "HIGH"
    assert disk_finding.confidence >= 0.95
    assert any("ENOSPC" in ev for ev in disk_finding.evidence)
    assert any("/scratch" in obs for obs in disk_finding.observed)
    assert any("unable to write temporary frame buffers" in inf.lower() for inf in disk_finding.inferred)


# ── Scenario 5: Driver Crash / Unresponsive ───────────────────────────────────

def test_scenario_5_driver_failure(hw_agent):
    """Scenario 5: Detects GPU driver crash, lost nvidia-smi communication, and Xid 61."""
    node_id = "node-driver-failure"

    drv = get_driver_status(node_id, store=hw_agent.store)
    assert drv["available"] is True
    assert drv["is_driver_responsive"] is False
    assert any(xid["code"] == 61 for xid in drv["xid_errors"])

    gpu = get_gpu_metrics(node_id, store=hw_agent.store)
    assert gpu["available"] is False  # nvidia-smi failed to talk to driver

    report = hw_agent.analyze_node(node_id)
    driver_finding = next(f for f in report.findings if f.finding_type == "DRIVER_FAILURE")

    assert driver_finding.severity == "CRITICAL"
    assert driver_finding.confidence >= 0.95
    assert any("unresponsive" in ev.lower() for ev in driver_finding.evidence)
    assert any("xid 61" in ev.lower() for ev in driver_finding.evidence)
    assert any("reboot required" in inf.lower() or "unrecoverable exception" in inf.lower() for inf in driver_finding.inferred)


# ── Scenario 6: Unavailable Telemetry (Anti-Hallucination) ───────────────────

def test_scenario_6_unavailable_telemetry_no_hallucination(hw_agent):
    """Scenario 6: Verifies agent returns 0.0 confidence and NO invented evidence for unregistered node."""
    node_id = "non_existent_blade_999"

    # 1. Tools return available=False
    health = get_node_health(node_id, store=hw_agent.store)
    assert health["available"] is False
    assert "No telemetry stream" in health["reason"]

    gpu = get_gpu_metrics(node_id, store=hw_agent.store)
    assert gpu["available"] is False

    cpu = get_cpu_metrics(node_id, store=hw_agent.store)
    assert cpu["available"] is False

    disk = get_disk_metrics(node_id, store=hw_agent.store)
    assert disk["available"] is False

    # 2. Agent analysis
    report = hw_agent.analyze_node(node_id)
    assert report.telemetry_available is False
    assert report.overall_confidence == 0.0
    assert len(report.findings) == 1

    finding = report.findings[0]
    assert finding.finding_type == "TELEMETRY_UNAVAILABLE"
    assert finding.confidence == 0.0
    assert len(finding.evidence) == 0  # STRICT: Zero invented evidence
    assert len(finding.observed) == 0  # No observations claimed
    assert len(finding.unknown) >= 1   # Explicitly acknowledges unknown state


# ── Scenario 7: Repeated Node Failures ────────────────────────────────────────

def test_scenario_7_repeated_node_failures(hw_agent):
    """Scenario 7: Identifies repeated failure history on degraded or unhealthy nodes."""
    node_id = "node-overheating"  # 4 consecutive failures

    report = hw_agent.analyze_node(node_id)
    repeated_finding = next(f for f in report.findings if f.finding_type == "REPEATED_NODE_FAILURES")

    assert repeated_finding.confidence >= 0.90
    assert any("4 consecutive job failures" in ev for ev in repeated_finding.evidence)
    assert any("persistent instability" in inf.lower() for inf in repeated_finding.inferred)


# ── Scenario 8: Renderer & CUDA Compatibility ─────────────────────────────────

def test_scenario_8_renderer_incompatibility(hw_agent):
    """Scenario 8: Identifies mismatch when requested renderer is unsupported by node driver."""
    node_id = "node-overheating"  # only supports arnold-7.2.4, vray-6.0

    report = hw_agent.analyze_node(node_id, context={"renderer": "renderman-26.0"})
    compat_finding = next(f for f in report.findings if f.finding_type == "RENDERER_INCOMPATIBILITY")

    assert compat_finding.confidence >= 0.90
    assert any("renderman-26.0" in ev for ev in compat_finding.evidence)
    assert any("not compatible" in ev.lower() for ev in compat_finding.evidence)


# ── Scenario 9: Google ADK Supervisor Contract Integration ───────────────────

@pytest.mark.asyncio
async def test_scenario_9_supervisor_integration_contract(hw_agent):
    """Scenario 9: Verifies that HardwareDiagnosticAgent implements the ADK BaseSpecialistAgent investigate contract."""
    event = {
        "event_id": "evt-hw-001",
        "source": "deadline",
        "event_type": "NODE_UNHEALTHY",
        "node_id": "node-gpu-oom",
        "error_details": {
            "error_code": "GPU_OUT_OF_MEMORY",
            "message": "CUDA out of memory while allocating buffer",
        },
    }
    specialist_report = await hw_agent.investigate("inc-hw-100", event)

    assert specialist_report.agent_name == "HardwareDiagnosticAgent"
    assert specialist_report.status == "SUCCESS"
    assert len(specialist_report.findings) >= 1
    assert len(specialist_report.evidence) >= 1
    assert len(specialist_report.hypotheses) >= 1

    first_finding = specialist_report.findings[0]
    assert first_finding.agent_name == "HardwareDiagnosticAgent"
    assert first_finding.category == "hardware"
    assert first_finding.confidence >= 0.95
    assert "observed" in first_finding.details
    assert "inferred" in first_finding.details
    assert "unknown" in first_finding.details


# ── Scenario 10: Non-Execution of Remediation Actions ─────────────────────────

def test_scenario_10_agent_does_not_execute_remediation(hw_agent):
    """Scenario 10: Strictly verifies agent only produces diagnostics and never triggers execution/remediation."""
    report = hw_agent.analyze_node("node-gpu-oom")
    report_dict = report.model_dump()

    # Agent output must not contain remediation execution payloads
    assert "remediation" not in report_dict
    assert "execute" not in report_dict
    assert "action" not in report_dict
    assert "mcp" not in report_dict
    assert "reboot" not in report_dict
    assert "quarantine" not in report_dict
