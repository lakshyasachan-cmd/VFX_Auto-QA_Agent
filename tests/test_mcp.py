"""
Comprehensive test suite for the MCP Integration subsystem.
Tests cover:
1. Valid action execution with verified policy approval
2. Parameter schema validation errors
3. Unauthorized caller/actor rejection
4. Missing governance approval rejection
5. Action identity mismatch rejection (approving action A, invoking tool B)
6. Duplicate / replay execution prevention
7. Controlled tool failure handling and audit logging
8. Schema compliance and output format for all 8 mock tools
9. Direct untrusted LLM invocation blocked (missing MCPExecutionContext)
10. REST API endpoints (/api/v1/mcp/tools and /api/v1/mcp/execute)
"""

import pytest
from fastapi.testclient import TestClient

from backend.governance.policy_engine import PolicyEngine
from backend.governance.service import GovernanceService
from backend.main import app
from backend.mcp.gateway import MCPExecutionGateway
from backend.mcp.schemas import (
    AssignPipelineTDParams,
    CreateIncidentParams,
    GeneratePostmortemParams,
    GetJobStatusParams,
    GetNodeHealthParams,
    MCPExecutionContext,
    MCPToolCallRequest,
    NotifyTeamParams,
    RetryRenderJobParams,
    ToolName,
    UpdateShotStatusParams,
)
from backend.mcp.server import MCPServer
from backend.mcp.tools import VFXToolImplementations


@pytest.fixture
def governance_svc() -> GovernanceService:
    """Provide clean isolated governance service."""
    return GovernanceService(policy_engine=PolicyEngine())


@pytest.fixture
def mcp_server_instance(governance_svc: GovernanceService) -> MCPServer:
    """Provide MCP server bound to test governance service."""
    return MCPServer(governance_svc=governance_svc)


@pytest.fixture
def client(mcp_server_instance: MCPServer, governance_svc: GovernanceService) -> TestClient:
    """TestClient with injected server and governance dependencies."""
    app.state.mcp_server = mcp_server_instance
    app.state.governance_service = governance_svc
    return TestClient(app, headers={"X-API-Key": "vfx-admin-secret-key-prod-001"})


# ─────────────────────────────────────────────────────────────
# 1. Valid Action Execution
# ─────────────────────────────────────────────────────────────

def test_valid_action_execution(mcp_server_instance: MCPServer, governance_svc: GovernanceService):
    """Test executing an action when policy approval has been granted."""
    # 1. Create and approve action in governance
    req = governance_svc.create_approval_request(
        action={
            "action": "RETRY_JOB",
            "parameters": {"job_id": "job-1042", "node_class": "gpu-80gb"},
            "confidence": 0.95,
            "risk": "LOW",
        },
        incident_id="inc-mcp-01",
    )
    # Auto-approved or explicitly approved
    if req.status != "AUTO_APPROVED":
        req = governance_svc.approve_action(req.approval_id, actor="pipeline_supervisor")

    # 2. Call MCP tool with valid execution context
    context = MCPExecutionContext(
        approval_id=req.approval_id,
        actor="orchestrator_service",
        incident_id="inc-mcp-01",
    )

    response = mcp_server_instance.call_tool(
        tool_name="retry_render_job",
        parameters={"job_id": "job-1042", "node_class": "gpu-80gb"},
        context=context,
    )

    assert response.success is True
    assert response.tool_name == "retry_render_job"
    assert response.data is not None
    # Verify required specification contract
    assert response.data["success"] is True
    assert response.data["job_id"] == "job-1042"
    assert "gpu-80gb" in response.data["new_node"]
    assert response.data["status"] == "QUEUED"
    assert response.audit_id is not None


# ─────────────────────────────────────────────────────────────
# 2. Invalid Parameter Validation
# ─────────────────────────────────────────────────────────────

def test_invalid_parameters(mcp_server_instance: MCPServer, governance_svc: GovernanceService):
    """Test that invalid parameters fail validation and do not execute."""
    req = governance_svc.create_approval_request(
        action={"action": "RETRY_JOB", "confidence": 0.95, "risk": "LOW"},
        incident_id="inc-mcp-02",
    )

    context = MCPExecutionContext(
        approval_id=req.approval_id,
        actor="orchestrator_service",
    )

    # Missing mandatory job_id or invalid types
    response = mcp_server_instance.call_tool(
        tool_name="retry_render_job",
        parameters={"unexpected_param": "invalid", "priority_boost": 9999},  # extra forbid + priority_boost > 100
        context=context,
    )

    assert response.success is False
    assert "Parameter validation failed" in response.error
    assert response.audit_id is not None


# ─────────────────────────────────────────────────────────────
# 3. Unauthorized Action
# ─────────────────────────────────────────────────────────────

def test_unauthorized_action(mcp_server_instance: MCPServer, governance_svc: GovernanceService):
    """Test execution rejection when actor is anonymous/untrusted or auth token is invalid."""
    req = governance_svc.create_approval_request(
        action={"action": "NOTIFY_TEAM", "confidence": 0.95, "risk": "LOW"},
        incident_id="inc-mcp-03",
    )

    # Anonymous or empty actor
    context_untrusted = MCPExecutionContext(
        approval_id=req.approval_id,
        actor="untrusted",
    )
    res1 = mcp_server_instance.call_tool(
        tool_name="notify_team",
        parameters={"channel": "#pipeline", "message": "Alert"},
        context=context_untrusted,
    )
    assert res1.success is False
    assert "Unauthorized actor" in res1.error

    # Bad auth token
    context_bad_token = MCPExecutionContext(
        approval_id=req.approval_id,
        actor="orchestrator_service",
        auth_token="invalid_token",
    )
    res2 = mcp_server_instance.call_tool(
        tool_name="notify_team",
        parameters={"channel": "#pipeline", "message": "Alert"},
        context=context_bad_token,
    )
    assert res2.success is False
    assert "Unauthorized" in res2.error


# ─────────────────────────────────────────────────────────────
# 4. Missing Approval
# ─────────────────────────────────────────────────────────────

def test_missing_approval(mcp_server_instance: MCPServer, governance_svc: GovernanceService):
    """Test rejection when approval record does not exist or is not approved."""
    # 1. Non-existent approval ID
    context_missing = MCPExecutionContext(
        approval_id="non-existent-approval-id",
        actor="orchestrator_service",
    )
    res1 = mcp_server_instance.call_tool(
        tool_name="update_shot_status",
        parameters={"project": "PRJ", "sequence": "sq01", "shot": "sh001", "new_status": "review"},
        context=context_missing,
    )
    assert res1.success is False
    assert "does not exist" in res1.error

    # 2. Pending approval (not yet approved by human)
    req_pending = governance_svc.create_approval_request(
        action={"action": "MODIFY_PRODUCTION_SCENE", "confidence": 0.85, "risk": "HIGH"},
        incident_id="inc-mcp-04",
    )
    assert req_pending.status == "PENDING"

    context_pending = MCPExecutionContext(
        approval_id=req_pending.approval_id,
        actor="orchestrator_service",
    )
    res2 = mcp_server_instance.call_tool(
        tool_name="update_shot_status",
        parameters={"project": "PRJ", "sequence": "sq01", "shot": "sh001", "new_status": "review"},
        context=context_pending,
    )
    assert res2.success is False
    assert "must be APPROVED" in res2.error


# ─────────────────────────────────────────────────────────────
# 5. Action Identity Mismatch
# ─────────────────────────────────────────────────────────────

def test_action_identity_mismatch(mcp_server_instance: MCPServer, governance_svc: GovernanceService):
    """Test that approving action A (e.g. RETRY_JOB) cannot be used to invoke tool B (e.g. UPDATE_SHOT_STATUS)."""
    req = governance_svc.create_approval_request(
        action={"action": "RETRY_JOB", "confidence": 0.95, "risk": "LOW"},
        incident_id="inc-mcp-05",
    )

    context = MCPExecutionContext(
        approval_id=req.approval_id,
        actor="orchestrator_service",
    )

    # Attempt to invoke update_shot_status using the RETRY_JOB approval
    response = mcp_server_instance.call_tool(
        tool_name="update_shot_status",
        parameters={"project": "PRJ", "sequence": "sq01", "shot": "sh001", "new_status": "review"},
        context=context,
    )

    assert response.success is False
    assert "Action identity mismatch" in response.error


# ─────────────────────────────────────────────────────────────
# 6. Duplicate / Replay Execution
# ─────────────────────────────────────────────────────────────

def test_duplicate_execution_blocked(mcp_server_instance: MCPServer, governance_svc: GovernanceService):
    """Test that an approved action cannot be re-executed multiple times."""
    req = governance_svc.create_approval_request(
        action={"action": "CREATE_INCIDENT", "confidence": 0.95, "risk": "LOW"},
        incident_id="inc-mcp-06",
    )

    context = MCPExecutionContext(
        approval_id=req.approval_id,
        actor="orchestrator_service",
    )

    # First execution succeeds
    res1 = mcp_server_instance.call_tool(
        tool_name="create_incident",
        parameters={"title": "Test Incident", "description": "Crash on node blade"},
        context=context,
    )
    assert res1.success is True

    # Replay/duplicate attempt with same approval ID is blocked
    res2 = mcp_server_instance.call_tool(
        tool_name="create_incident",
        parameters={"title": "Test Incident", "description": "Crash on node blade"},
        context=context,
    )
    assert res2.success is False
    assert "Duplicate execution blocked" in res2.error


# ─────────────────────────────────────────────────────────────
# 7. Controlled Tool Failure Handling
# ─────────────────────────────────────────────────────────────

def test_tool_failure_handling(governance_svc: GovernanceService):
    """Test that tool exceptions are caught cleanly and recorded in the audit log."""
    # Create custom registry with a failing tool
    def faulty_handler(params):
        raise ConnectionResetError("Render farm connection timed out.")

    custom_registry = {
        "retry_render_job": (RetryRenderJobParams, faulty_handler),
    }

    server = MCPServer(governance_svc=governance_svc, custom_tool_registry=custom_registry)
    req = governance_svc.create_approval_request(
        action={"action": "RETRY_JOB", "confidence": 0.95, "risk": "LOW"},
        incident_id="inc-mcp-07",
    )

    context = MCPExecutionContext(
        approval_id=req.approval_id,
        actor="orchestrator_service",
    )

    response = server.call_tool(
        tool_name="retry_render_job",
        parameters={"job_id": "job-999"},
        context=context,
    )

    assert response.success is False
    assert "Tool execution failed" in response.error
    assert "Render farm connection timed out" in response.error
    assert response.audit_id is not None

    # Verify audit entry was created for failure
    audit_entry = next(r for r in server.gateway.audit_records if r["id"] == response.audit_id)
    assert audit_entry["status"] == "FAILED"
    assert audit_entry["action"] == "TOOL_EXECUTION_FAILURE"


# ─────────────────────────────────────────────────────────────
# 8. All 8 Tools Return Expected Schema
# ─────────────────────────────────────────────────────────────

def test_all_8_mock_tools_functional(mcp_server_instance: MCPServer, governance_svc: GovernanceService):
    """Verify all 8 VFX workflow tools execute cleanly and match schemas."""
    # 1. get_job_status
    p1 = GetJobStatusParams(job_id="job-101")
    r1 = VFXToolImplementations.get_job_status(p1)
    assert r1["success"] is True and r1["job_id"] == "job-101"

    # 2. get_node_health
    p2 = GetNodeHealthParams(node_id="node-12")
    r2 = VFXToolImplementations.get_node_health(p2)
    assert r2["success"] is True and r2["node_id"] == "node-12"

    # 3. retry_render_job
    p3 = RetryRenderJobParams(job_id="job-101", node_class="gpu-80gb")
    r3 = VFXToolImplementations.retry_render_job(p3)
    assert r3["success"] is True and r3["status"] == "QUEUED"

    # 4. assign_pipeline_td
    p4 = AssignPipelineTDParams(incident_id="inc-1", td_name="alex_td", department="lighting")
    r4 = VFXToolImplementations.assign_pipeline_td(p4)
    assert r4["success"] is True and r4["status"] == "ASSIGNED"

    # 5. update_shot_status
    p5 = UpdateShotStatusParams(project="PRJ", sequence="sq01", shot="sh001", new_status="review")
    r5 = VFXToolImplementations.update_shot_status(p5)
    assert r5["success"] is True and r5["new_status"] == "review"

    # 6. create_incident
    p6 = CreateIncidentParams(title="Arnold GPU OOM", description="Crash on frame 105")
    r6 = VFXToolImplementations.create_incident(p6)
    assert r6["success"] is True and "INC-" in r6["ticket_id"]

    # 7. notify_team
    p7 = NotifyTeamParams(channel="#lighting-lead", message="Shot ready for review")
    r7 = VFXToolImplementations.notify_team(p7)
    assert r7["success"] is True and r7["status"] == "DELIVERED"

    # 8. generate_postmortem
    p8 = GeneratePostmortemParams(incident_id="inc-1", title="OOM Postmortem", root_cause="VDB Cache Overrun", summary="VDB asset was uncompressed.")
    r8 = VFXToolImplementations.generate_postmortem(p8)
    assert r8["success"] is True and r8["status"] == "PUBLISHED"


# ─────────────────────────────────────────────────────────────
# 9. Direct Untrusted LLM Calls Blocked
# ─────────────────────────────────────────────────────────────

def test_direct_untrusted_llm_call_blocked(mcp_server_instance: MCPServer):
    """Ensure that calling an MCP tool directly without execution context is blocked."""
    response = mcp_server_instance.call_tool(
        tool_name="retry_render_job",
        parameters={"job_id": "job-100"},
        context=None,  # No governance context provided
    )

    assert response.success is False
    assert "Untrusted direct tool call blocked" in response.error
    assert response.audit_id is not None


# ─────────────────────────────────────────────────────────────
# 10. REST API Endpoints
# ─────────────────────────────────────────────────────────────

def test_mcp_api_endpoints(client: TestClient, governance_svc: GovernanceService):
    """Test GET /api/v1/mcp/tools and POST /api/v1/mcp/execute."""
    # List tools
    res_list = client.get("/api/v1/mcp/tools")
    assert res_list.status_code == 200
    tools = res_list.json()
    assert len(tools) == 8
    tool_names = [t["name"] for t in tools]
    assert "retry_render_job" in tool_names
    assert "assign_pipeline_td" in tool_names

    # Get single tool
    res_single = client.get("/api/v1/mcp/tools/retry_render_job")
    assert res_single.status_code == 200
    assert res_single.json()["name"] == "retry_render_job"

    # 404 for unknown tool
    res_unknown = client.get("/api/v1/mcp/tools/unknown_tool")
    assert res_unknown.status_code == 404

    # Execute tool via API
    req = governance_svc.create_approval_request(
        action={"action": "ASSIGN_PIPELINE_TD", "confidence": 0.95, "risk": "LOW"},
        incident_id="inc-api-mcp",
    )

    payload = {
        "tool_name": "assign_pipeline_td",
        "parameters": {
            "incident_id": "inc-api-mcp",
            "td_name": "marcus_lead",
            "department": "compositing",
            "priority": "high",
        },
        "context": {
            "approval_id": req.approval_id,
            "actor": "api_client_service",
            "incident_id": "inc-api-mcp",
        },
    }

    res_exec = client.post("/api/v1/mcp/execute", json=payload)
    assert res_exec.status_code == 200
    exec_data = res_exec.json()
    assert exec_data["success"] is True
    assert exec_data["data"]["status"] == "ASSIGNED"
    assert exec_data["data"]["td_name"] == "marcus_lead"
