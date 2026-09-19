"""
Comprehensive test suite for IBM watsonx Orchestrate Integration.
Covers:
1. Default mock mode (WATSONX_MOCK=true): no external calls, returns expected VFX contracts.
2. All 8 VFX tools dispatching cleanly through WatsonxWorkflowAdapter.
3. Live mode configuration validation: raises WatsonxConfigurationError when credentials missing.
4. Live client execution with mocked HTTP transport (success path).
5. Transient error retry mechanism: retries on 503 / network drops with backoff.
6. Timeout handling: raises WatsonxTimeoutError after max attempts.
7. Policy engine invariance: unapproved actions are rejected at the policy/gateway layer before reaching watsonx.
8. Audit logging: verifies immutable audit records generated for watsonx workflow executions.
"""

import httpx
import pytest

from backend.governance.policy_engine import PolicyEngine
from backend.governance.service import GovernanceService
from backend.integrations.watsonx.adapter import WatsonxWorkflowAdapter
from backend.integrations.watsonx.client import WatsonxOrchestrateClient
from backend.integrations.watsonx.config import WatsonxSettings
from backend.integrations.watsonx.errors import (
    WatsonxAuthenticationError,
    WatsonxConfigurationError,
    WatsonxError,
    WatsonxTimeoutError,
    WatsonxWorkflowExecutionError,
)
from backend.mcp.gateway import MCPExecutionGateway
from backend.mcp.schemas import (
    AssignPipelineTDParams,
    CreateIncidentParams,
    GeneratePostmortemParams,
    GetJobStatusParams,
    GetNodeHealthParams,
    MCPExecutionContext,
    NotifyTeamParams,
    RetryRenderJobParams,
    UpdateShotStatusParams,
)
from backend.mcp.server import MCPServer


@pytest.fixture
def governance_svc() -> GovernanceService:
    return GovernanceService(policy_engine=PolicyEngine())


# ─────────────────────────────────────────────────────────────
# 1. Default Mock Mode Active & No External Calls
# ─────────────────────────────────────────────────────────────

def test_watsonx_mock_mode_active_by_default():
    """Verify that default settings load mock_mode=True and execute locally."""
    settings = WatsonxSettings(mock_mode=True)
    adapter = WatsonxWorkflowAdapter(settings=settings)

    # Calling retry_render_job in mock mode should return immediately with valid format
    params = RetryRenderJobParams(job_id="job-mock-01", node_class="gpu-80gb")
    result = adapter.retry_render_job(params)

    assert result["success"] is True
    assert result["job_id"] == "job-mock-01"
    assert "gpu-80gb" in result["new_node"]
    assert result["status"] == "QUEUED"
    # Verify audit record created in adapter
    assert len(adapter.audit_records) == 1
    assert adapter.audit_records[0]["mock_mode"] is True


# ─────────────────────────────────────────────────────────────
# 2. All 8 Tools via WatsonxWorkflowAdapter
# ─────────────────────────────────────────────────────────────

def test_all_8_tools_via_watsonx_adapter():
    """Verify that all 8 tools execute cleanly through the adapter in mock mode."""
    adapter = WatsonxWorkflowAdapter(settings=WatsonxSettings(mock_mode=True))

    # 1. retry_render_job
    r1 = adapter.retry_render_job(RetryRenderJobParams(job_id="job-101"))
    assert r1["success"] is True and r1["status"] == "QUEUED"

    # 2. assign_pipeline_td
    r2 = adapter.assign_pipeline_td(AssignPipelineTDParams(incident_id="inc-1", td_name="alex_lead"))
    assert r2["success"] is True and r2["status"] == "ASSIGNED"

    # 3. update_shot_status
    r3 = adapter.update_shot_status(UpdateShotStatusParams(project="PRJ", sequence="sq01", shot="sh01", new_status="review"))
    assert r3["success"] is True and r3["new_status"] == "review"

    # 4. create_incident
    r4 = adapter.create_incident(CreateIncidentParams(title="Crash", description="OOM"))
    assert r4["success"] is True and "INC-" in r4["ticket_id"]

    # 5. notify_team
    r5 = adapter.notify_team(NotifyTeamParams(channel="#alerts", message="Check farm"))
    assert r5["success"] is True and r5["status"] == "DELIVERED"

    # 6. generate_postmortem
    r6 = adapter.generate_postmortem(GeneratePostmortemParams(incident_id="inc-1", title="PM", root_cause="OOM", summary="Summary"))
    assert r6["success"] is True and r6["status"] == "PUBLISHED"

    # 7. get_job_status
    r7 = adapter.get_job_status(GetJobStatusParams(job_id="job-101"))
    assert r7["success"] is True and r7["job_id"] == "job-101"

    # 8. get_node_health
    r8 = adapter.get_node_health(GetNodeHealthParams(node_id="node-1"))
    assert r8["success"] is True and r8["node_id"] == "node-1"


# ─────────────────────────────────────────────────────────────
# 3. Live Mode Configuration Validation
# ─────────────────────────────────────────────────────────────

def test_watsonx_live_mode_requires_credentials():
    """Disabling mock mode without credentials raises WatsonxConfigurationError."""
    settings = WatsonxSettings(
        mock_mode=False,
        api_key=None,
        instance_url=None,
    )
    client = WatsonxOrchestrateClient(settings=settings)

    with pytest.raises(WatsonxConfigurationError) as exc_info:
        client.validate_configuration()

    assert "WATSONX_API_KEY" in exc_info.value.details["missing_keys"]
    assert "WATSONX_INSTANCE_URL" in exc_info.value.details["missing_keys"]


# ─────────────────────────────────────────────────────────────
# 4. Live Client Execution with Mocked HTTP Transport
# ─────────────────────────────────────────────────────────────

def test_watsonx_live_client_success():
    """Test authenticated execution against watsonx HTTP endpoint with mocked responses."""
    def handler(request: httpx.Request) -> httpx.Response:
        if "iam.cloud.ibm.com" in str(request.url):
            return httpx.Response(200, json={"access_token": "mock-iam-token-12345", "expires_in": 3600})
        if "/v1/skills/retry_render_job_skill/run" in str(request.url):
            assert request.headers["Authorization"] == "Bearer mock-iam-token-12345"
            return httpx.Response(200, json={
                "outputs": {
                    "job_id": "job-live-99",
                    "new_node": "node-blade-80gb-05",
                    "status": "QUEUED",
                }
            })
        return httpx.Response(404)

    mock_transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=mock_transport)

    settings = WatsonxSettings(
        mock_mode=False,
        api_key="valid-api-key",
        instance_url="https://api.watsonx.ai",
    )
    client = WatsonxOrchestrateClient(settings=settings, http_client=http_client)
    adapter = WatsonxWorkflowAdapter(settings=settings, client=client)

    result = adapter.retry_render_job(RetryRenderJobParams(job_id="job-live-99", node_class="gpu-80gb"))
    assert result["success"] is True
    assert result["job_id"] == "job-live-99"
    assert result["new_node"] == "node-blade-80gb-05"
    assert result["status"] == "QUEUED"


# ─────────────────────────────────────────────────────────────
# 5. Transient Error Retry Mechanism
# ─────────────────────────────────────────────────────────────

def test_watsonx_retry_on_transient_failure():
    """Test that client retries on 503 Service Unavailable and succeeds once recovered."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        if "iam.cloud.ibm.com" in str(request.url):
            return httpx.Response(200, json={"access_token": "mock-token", "expires_in": 3600})

        call_count += 1
        if call_count < 2:
            return httpx.Response(503, text="Service Temporarily Unavailable")
        return httpx.Response(200, json={"outputs": {"status": "SUCCESS", "job_id": "job-retry"}})

    mock_transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=mock_transport)

    settings = WatsonxSettings(
        mock_mode=False,
        api_key="test-key",
        instance_url="https://api.watsonx.ai",
        max_retries=3,
        retry_backoff_factor=0.01,
    )
    client = WatsonxOrchestrateClient(settings=settings, http_client=http_client)
    res = client.run_workflow("test_skill", {"key": "val"})

    assert call_count == 2
    assert res["outputs"]["status"] == "SUCCESS"


# ─────────────────────────────────────────────────────────────
# 6. Timeout Handling
# ─────────────────────────────────────────────────────────────

def test_watsonx_timeout_handling():
    """Verify that continuous timeouts raise WatsonxTimeoutError after retries."""
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        if "iam.cloud.ibm.com" in str(request.url):
            return httpx.Response(200, json={"access_token": "mock-token", "expires_in": 3600})
        raise httpx.ReadTimeout("Socket timeout connecting to watsonx")

    mock_transport = httpx.MockTransport(timeout_handler)
    http_client = httpx.Client(transport=mock_transport)

    settings = WatsonxSettings(
        mock_mode=False,
        api_key="test-key",
        instance_url="https://api.watsonx.ai",
        max_retries=2,
        retry_backoff_factor=0.01,
        timeout_seconds=5.0,
    )
    client = WatsonxOrchestrateClient(settings=settings, http_client=http_client)

    with pytest.raises(WatsonxTimeoutError) as exc_info:
        client.run_workflow("test_skill", {})

    assert exc_info.value.error_code == "WATSONX_TIMEOUT"


# ─────────────────────────────────────────────────────────────
# 7. Policy Engine Invariance: watsonx Cannot Bypass Policy
# ─────────────────────────────────────────────────────────────

def test_watsonx_cannot_bypass_policy_engine(governance_svc: GovernanceService):
    """
    Ensure the application policy engine gates all execution.
    An unapproved action or invalid execution context is stopped by MCPExecutionGateway
    and never reaches the watsonx adapter.
    """
    server = MCPServer(governance_svc=governance_svc)

    # 1. Direct invocation without approval context
    res1 = server.call_tool(
        tool_name="retry_render_job",
        parameters={"job_id": "job-100"},
        context=None,
    )
    assert res1.success is False
    assert "Untrusted direct tool call blocked" in res1.error

    # 2. Pending approval blocked by policy
    req_pending = governance_svc.create_approval_request(
        action={"action": "MODIFY_PRODUCTION_SCENE", "confidence": 0.85, "risk": "HIGH"},
        incident_id="inc-sec-01",
    )
    context_pending = MCPExecutionContext(
        approval_id=req_pending.approval_id,
        actor="authorized_supervisor",
    )
    res2 = server.call_tool(
        tool_name="update_shot_status",
        parameters={"project": "PRJ", "sequence": "sq01", "shot": "sh01", "new_status": "review"},
        context=context_pending,
    )
    assert res2.success is False
    assert "must be APPROVED" in res2.error

    # 3. Unauthorized actor blocked
    req_approved = governance_svc.create_approval_request(
        action={"action": "NOTIFY_TEAM", "confidence": 0.95, "risk": "LOW"},
        incident_id="inc-sec-02",
    )
    context_unauthorized = MCPExecutionContext(
        approval_id=req_approved.approval_id,
        actor="untrusted",
    )
    res3 = server.call_tool(
        tool_name="notify_team",
        parameters={"channel": "#pipeline", "message": "Alert"},
        context=context_unauthorized,
    )
    assert res3.success is False
    assert "Unauthorized actor" in res3.error


# ─────────────────────────────────────────────────────────────
# 8. End-to-End Execution Flow via MCP Gateway into watsonx
# ─────────────────────────────────────────────────────────────

def test_e2e_flow_governance_to_mcp_to_watsonx(governance_svc: GovernanceService):
    """
    Verify complete flow:
    Remediation Plan -> Policy Engine -> Approval -> MCP -> watsonx Orchestrate
    """
    server = MCPServer(governance_svc=governance_svc)

    # Create and approve request
    req = governance_svc.create_approval_request(
        action={
            "action": "RETRY_JOB",
            "parameters": {"job_id": "job-vfx-e2e", "node_class": "gpu-80gb"},
            "confidence": 0.95,
            "risk": "LOW",
        },
        incident_id="inc-e2e-01",
    )
    if req.status != "AUTO_APPROVED":
        req = governance_svc.approve_action(req.approval_id, actor="lead_pipeline_td")

    context = MCPExecutionContext(
        approval_id=req.approval_id,
        actor="governed_agent_orchestrator",
        incident_id="inc-e2e-01",
    )

    response = server.call_tool(
        tool_name="retry_render_job",
        parameters={"job_id": "job-vfx-e2e", "node_class": "gpu-80gb"},
        context=context,
    )

    assert response.success is True
    assert response.data["status"] == "QUEUED"
    assert response.data["job_id"] == "job-vfx-e2e"
    assert response.audit_id is not None
