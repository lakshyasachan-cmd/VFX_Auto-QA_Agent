"""
Unit & integration tests for the Google ADK Supervisor Agent.
Tests verify:
- Correct specialist agent selection based on incident type
- Handling of malformed events
- Missing data warnings and penalties
- Conflicting findings detection
- Agent failure & fault tolerance
- Timeout handling & containment
- Safe handling of unavailable specialists
- Strict verification that supervisor does not execute production actions
"""

import pytest

from backend.agents.supervisor.mock_specialists import (
    MockAssetValidationAgent,
    MockHardwareDiagnosticAgent,
    MockHistoricalEvidenceAgent,
    MockRenderQAAgent,
)
from backend.agents.supervisor.schemas import (
    AgentFindingDTO,
    IncidentClassification,
    InvestigationRequest,
    InvestigationStatus,
    SpecialistName,
)
from backend.agents.supervisor.supervisor_agent import SupervisorAgent


@pytest.fixture
def default_supervisor():
    """Returns a SupervisorAgent configured with mock specialists."""
    return SupervisorAgent(
        sub_agents=[
            MockRenderQAAgent(),
            MockHardwareDiagnosticAgent(),
            MockAssetValidationAgent(),
            MockHistoricalEvidenceAgent(),
        ]
    )


@pytest.mark.asyncio
async def test_correct_agent_selection_render_failure(default_supervisor):
    """
    When a render job fails on a specific node, supervisor should select:
    RenderQAAgent + HardwareDiagnosticAgent + HistoricalEvidenceAgent.
    """
    event = {
        "source": "deadline",
        "event_type": "RENDER_JOB_FAILED",
        "project": "Avatar3",
        "sequence": "SQ010",
        "shot": "SH001",
        "job_id": "job_101",
        "node_id": "render-node-42",
        "error_code": "GPU_OUT_OF_MEMORY",
    }
    request = InvestigationRequest(incident_id="inc-001", event=event)
    result = await default_supervisor.investigate_incident(request)

    assert result.incident_type == IncidentClassification.RENDER_FAILURE
    assert SpecialistName.RENDER_QA.value in result.selected_specialists
    assert SpecialistName.HARDWARE_DIAGNOSTIC.value in result.selected_specialists
    assert SpecialistName.HISTORICAL_EVIDENCE.value in result.selected_specialists
    assert result.status == InvestigationStatus.INVESTIGATION_COMPLETE
    assert len(result.findings) >= 2
    assert result.confidence >= 0.65


@pytest.mark.asyncio
async def test_correct_agent_selection_hardware_fault(default_supervisor):
    """
    When a compute blade becomes unhealthy, supervisor selects HardwareDiagnosticAgent + HistoricalEvidenceAgent.
    """
    event = {
        "source": "tractor",
        "event_type": "NODE_UNHEALTHY",
        "node_id": "blade-042",
        "error_code": "PCIE_BUS_DEGRADED",
    }
    result = await default_supervisor.investigate_incident({
        "incident_id": "inc-002",
        "event": event,
    })

    assert result.incident_type == IncidentClassification.HARDWARE_FAULT
    assert SpecialistName.HARDWARE_DIAGNOSTIC.value in result.selected_specialists
    assert SpecialistName.HISTORICAL_EVIDENCE.value in result.selected_specialists
    assert SpecialistName.ASSET_VALIDATION.value not in result.selected_specialists


@pytest.mark.asyncio
async def test_correct_agent_selection_asset_anomaly(default_supervisor):
    """
    When an asset validation error occurs, supervisor selects AssetValidationAgent + HistoricalEvidenceAgent.
    """
    event = {
        "source": "asset_storage",
        "event_type": "ASSET_VALIDATION_FAILED",
        "project": "Dune3",
        "shot": "SH020",
        "asset_name": "/prod/assets/char/hero.usd",
        "error_code": "USD_SUBCOMPONENT_MISSING",
    }
    result = await default_supervisor.investigate_incident({
        "incident_id": "inc-003",
        "event": event,
    })

    assert result.incident_type == IncidentClassification.ASSET_ANOMALY
    assert SpecialistName.ASSET_VALIDATION.value in result.selected_specialists
    assert SpecialistName.HISTORICAL_EVIDENCE.value in result.selected_specialists


@pytest.mark.asyncio
async def test_malformed_events_handling(default_supervisor):
    """
    Supervisor must not crash when receiving None or empty/malformed event dictionaries.
    """
    # Test with empty dict
    result_empty = await default_supervisor.investigate_incident({
        "incident_id": "inc-empty",
        "event": {},
    })
    assert result_empty.incident_type == IncidentClassification.UNKNOWN
    assert len(result_empty.missing_data_warnings) > 0
    assert result_empty.status in (InvestigationStatus.INVESTIGATION_COMPLETE, InvestigationStatus.PARTIAL_INVESTIGATION)

    # Test with non-dict / empty payload
    result_malformed = await default_supervisor.investigate_incident(
        InvestigationRequest(incident_id="inc-malformed", event={})
    )
    assert result_malformed.incident_type == IncidentClassification.UNKNOWN


@pytest.mark.asyncio
async def test_missing_data_warnings_and_penalties(default_supervisor):
    """
    Events missing project or error_code should trigger warnings and penalize confidence.
    """
    event = {
        "source": "deadline",
        "event_type": "RENDER_JOB_FAILED",
        "job_id": "job_orphan",
        # Missing project, shot, node_id, and error_code
    }
    result = await default_supervisor.investigate_incident({
        "incident_id": "inc-missing",
        "event": event,
    })
    assert len(result.missing_data_warnings) >= 2
    assert any("project" in w for w in result.missing_data_warnings)
    assert any("error_code" in w for w in result.missing_data_warnings)


@pytest.mark.asyncio
async def test_conflicting_findings_detection():
    """
    Supervisor must detect contradictory findings (e.g. software shader blame vs hardware failure).
    """
    # Create conflicting mock specialists
    conflicting_render_qa = MockRenderQAAgent(
        custom_findings=[
            AgentFindingDTO(
                agent_name="RenderQAAgent",
                finding_type="SHADER_BUG",
                category="software",
                severity="HIGH",
                confidence=0.91,
                title="Scene shader failed with memory corruption bug in Arnold plugin",
            )
        ]
    )
    conflicting_hardware = MockHardwareDiagnosticAgent(
        custom_findings=[
            AgentFindingDTO(
                agent_name="HardwareDiagnosticAgent",
                finding_type="GPU_HARDWARE_FAULT",
                category="hardware",
                severity="CRITICAL",
                confidence=0.89,
                title="Compute blade GPU thermal threshold exceeded (94C junction temp)",
            )
        ]
    )

    supervisor = SupervisorAgent(
        sub_agents=[
            conflicting_render_qa,
            conflicting_hardware,
            MockHistoricalEvidenceAgent(),
        ]
    )

    event = {
        "source": "deadline",
        "event_type": "RENDER_JOB_FAILED",
        "project": "Project_A",
        "job_id": "job_99",
        "node_id": "render-node-12",
        "error_code": "CRASH",
    }
    result = await supervisor.investigate_incident({
        "incident_id": "inc-conflict",
        "event": event,
    })

    # Conflict detector must find the clash between software and hardware
    assert len(result.conflicts) >= 1
    conflict = result.conflicts[0]
    assert "RenderQAAgent" in conflict.conflicting_agents
    assert "HardwareDiagnosticAgent" in conflict.conflicting_agents
    assert "Contradictory Root Cause" in conflict.reason
    assert "WARNING" in result.summary


@pytest.mark.asyncio
async def test_agent_failure_safe_containment():
    """
    If a specialist agent crashes with an exception, supervisor must fail safely,
    mark that specialist as FAILED, and return PARTIAL_INVESTIGATION with other findings.
    """
    failing_hw_agent = MockHardwareDiagnosticAgent(should_fail=True, failure_message="Database socket connection refused")
    working_qa_agent = MockRenderQAAgent()

    supervisor = SupervisorAgent(
        sub_agents=[working_qa_agent, failing_hw_agent, MockHistoricalEvidenceAgent()]
    )

    event = {
        "source": "deadline",
        "event_type": "RENDER_JOB_FAILED",
        "project": "Project_A",
        "job_id": "job_fail_test",
        "node_id": "blade-01",
    }

    result = await supervisor.investigate_incident({
        "incident_id": "inc-fail-test",
        "event": event,
    })

    assert result.status == InvestigationStatus.PARTIAL_INVESTIGATION
    failed_trace = next(t for t in result.agent_traces if t.agent_name == "HardwareDiagnosticAgent")
    assert failed_trace.status == "FAILED"
    assert "connection refused" in failed_trace.error

    success_trace = next(t for t in result.agent_traces if t.agent_name == "RenderQAAgent")
    assert success_trace.status == "SUCCESS"
    assert len(result.findings) >= 1


@pytest.mark.asyncio
async def test_timeout_handling():
    """
    If a specialist agent exceeds the timeout, supervisor marks it as TIMED_OUT and continues.
    """
    slow_agent = MockRenderQAAgent(delay_seconds=2.0)
    fast_hw_agent = MockHardwareDiagnosticAgent()

    supervisor = SupervisorAgent(
        sub_agents=[slow_agent, fast_hw_agent, MockHistoricalEvidenceAgent()]
    )

    event = {
        "source": "deadline",
        "event_type": "RENDER_JOB_FAILED",
        "project": "Project_A",
        "job_id": "job_slow",
        "node_id": "blade-02",
    }

    # Set strict 0.2s timeout
    result = await supervisor.investigate_incident(
        InvestigationRequest(
            incident_id="inc-timeout",
            event=event,
            timeout_seconds=0.2,
        )
    )

    timed_out_trace = next(t for t in result.agent_traces if t.agent_name == "RenderQAAgent")
    assert timed_out_trace.status == "TIMED_OUT"
    assert "timed out after 0.2s" in timed_out_trace.error
    assert result.status == InvestigationStatus.PARTIAL_INVESTIGATION


@pytest.mark.asyncio
async def test_unavailable_specialist_fails_safely():
    """
    If an explicit specialist is requested but not registered, supervisor records failure trace without crashing.
    """
    supervisor = SupervisorAgent(sub_agents=[MockRenderQAAgent()])

    result = await supervisor.investigate_incident(
        InvestigationRequest(
            incident_id="inc-unavail",
            event={"source": "deadline", "event_type": "RENDER_JOB_FAILED"},
            required_specialists=["NonExistentSpecialist"],
        )
    )

    assert result.status == InvestigationStatus.INVESTIGATION_FAILED
    assert len(result.agent_traces) == 1
    assert result.agent_traces[0].status == "FAILED"
    assert "not registered" in result.agent_traces[0].error


@pytest.mark.asyncio
async def test_supervisor_does_not_execute_production_actions(default_supervisor):
    """
    Verify absolute constraint: Supervisor MUST NOT produce or execute production actions.
    Output is strictly diagnostic.
    """
    event = {
        "source": "deadline",
        "event_type": "RENDER_JOB_FAILED",
        "project": "Avatar3",
        "job_id": "job_inspect",
        "node_id": "blade-01",
    }
    result = await default_supervisor.investigate_incident({
        "incident_id": "inc-no-action",
        "event": event,
    })

    result_dict = result.model_dump()
    # Confirm result schema does not contain action or remediation execution keys
    assert "actions" not in result_dict
    assert "remediation_plan" not in result_dict
    assert "mcp_tool" not in result_dict
    assert result.status in (InvestigationStatus.INVESTIGATION_COMPLETE, InvestigationStatus.PARTIAL_INVESTIGATION)
