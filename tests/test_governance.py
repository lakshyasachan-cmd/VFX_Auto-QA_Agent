"""
Unit and integration tests for the AI Governance deterministic policy engine,
human-in-the-loop approvals, action modifications, immutable audit logging,
and REST endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.governance.policy_engine import PolicyEngine
from backend.governance.schemas import ApprovalStatus, GovernanceDecision
from backend.governance.service import GovernanceService


@pytest.fixture
def governance_svc():
    return GovernanceService(policy_engine=PolicyEngine())


@pytest.fixture
def client(governance_svc):
    # Set the test governance service instance on app state
    app.state.governance_service = governance_svc
    return TestClient(app, headers={"X-API-Key": "vfx-admin-secret-key-prod-001"})


# ---------------------------------------------------------------------------
# Policy Engine & Gating Tests
# ---------------------------------------------------------------------------

def test_auto_approval_low_risk_high_confidence(governance_svc):
    """
    RETRY_JOB with confidence >= 0.90 and risk LOW should be AUTO_APPROVED.
    """
    action = {
        "action": "RETRY_JOB",
        "reason": "Transient network timeout during render checkpoint",
        "risk": "LOW",
        "confidence": 0.95,
        "parameters": {"job_id": "job-101", "target_node": "node-05"},
    }
    
    result = governance_svc.evaluate_policy(action)
    assert result.decision == GovernanceDecision.AUTO_APPROVE
    assert result.requires_human_approval is False
    assert result.effective_risk == "LOW"
    
    # Create request and verify status
    approval = governance_svc.create_approval_request(
        action=action,
        incident_id="inc-001",
        source_agent="remediation_specialist",
    )
    assert approval.status == ApprovalStatus.AUTO_APPROVED
    assert approval.approved_by == "policy_engine_auto"


def test_human_approval_modify_production_scene(governance_svc):
    """
    MODIFY_PRODUCTION_SCENE must require HUMAN_APPROVAL deterministically,
    even if AI proposes confidence 0.99.
    """
    action = {
        "action": "MODIFY_PRODUCTION_SCENE",
        "reason": "Disable motion blur on corrupt geometry frame 1042",
        "risk": "HIGH",
        "confidence": 0.99,
        "parameters": {"scene_path": "/prod/shots/sq01/sh0010/lighting.usd"},
    }
    
    result = governance_svc.evaluate_policy(action)
    assert result.decision == GovernanceDecision.HUMAN_APPROVAL
    assert result.requires_human_approval is True
    
    approval = governance_svc.create_approval_request(
        action=action,
        incident_id="inc-002",
    )
    assert approval.status == ApprovalStatus.PENDING
    assert approval.approved_by is None


def test_human_approval_delete_asset(governance_svc):
    """
    DELETE_ASSET must require HUMAN_APPROVAL deterministically.
    """
    action = {
        "action": "DELETE_ASSET",
        "reason": "Remove orphaned cache file v002 to save disk space",
        "risk": "HIGH",
        "confidence": 0.92,
        "parameters": {"asset_path": "/prod/assets/chars/hero/cache/v002.vdb"},
    }
    
    result = governance_svc.evaluate_policy(action)
    assert result.decision == GovernanceDecision.HUMAN_APPROVAL
    assert result.requires_human_approval is True
    assert result.effective_risk in ["HIGH", "CRITICAL"]


def test_human_approval_critical_action(governance_svc):
    """
    Any CRITICAL action must require HUMAN_APPROVAL.
    """
    action = {
        "action": "DRAIN_COMPUTE_CLUSTER",
        "reason": "Thermal anomaly detected on blade chassis",
        "risk": "CRITICAL",
        "confidence": 0.98,
        "parameters": {"rack_id": "rack-b"},
    }
    
    result = governance_svc.evaluate_policy(action)
    assert result.decision == GovernanceDecision.HUMAN_APPROVAL
    assert result.effective_risk == "CRITICAL"
    assert result.requires_human_approval is True


def test_forbidden_action_rejection_overrides_high_confidence_ai(governance_svc):
    """
    Forbidden catastrophic actions (e.g. DELETE_DATABASE) must be REJECTED immediately,
    regardless of how high the LLM's confidence is (even 1.0).
    """
    action = {
        "action": "PURGE_PRODUCTION_STORAGE",
        "reason": "Free disk space immediately to save deadline",
        "risk": "CRITICAL",
        "confidence": 1.0,
        "parameters": {"mount": "/mnt/prod_storage"},
    }
    
    result = governance_svc.evaluate_policy(action)
    assert result.decision == GovernanceDecision.REJECT
    assert "Forbidden action" in result.reasoning
    
    approval = governance_svc.create_approval_request(
        action=action,
        incident_id="inc-003",
    )
    assert approval.status == ApprovalStatus.REJECTED


def test_all_risk_levels_classification(governance_svc):
    """Verify behavior and risk mapping across LOW, MEDIUM, HIGH, and CRITICAL."""
    # 1. LOW: NOTIFY_TEAM
    r_low = governance_svc.evaluate_policy({"action": "NOTIFY_TEAM", "confidence": 0.95})
    assert r_low.effective_risk == "LOW"
    assert r_low.decision == GovernanceDecision.AUTO_APPROVE

    # 2. MEDIUM: RESTART_RENDER_DAEMON
    r_med = governance_svc.evaluate_policy({"action": "RESTART_RENDER_DAEMON", "confidence": 0.85})
    assert r_med.effective_risk == "MEDIUM"
    assert r_med.decision == GovernanceDecision.HUMAN_APPROVAL  # Confidence < 0.90

    # 3. HIGH: OVERRIDE_FRAME_RANGE
    r_high = governance_svc.evaluate_policy({"action": "OVERRIDE_FRAME_RANGE", "confidence": 0.95})
    assert r_high.effective_risk == "HIGH"
    assert r_high.decision == GovernanceDecision.HUMAN_APPROVAL

    # 4. CRITICAL: PURGE_PRODUCTION_STORAGE
    r_crit = governance_svc.evaluate_policy({"action": "PURGE_PRODUCTION_STORAGE", "confidence": 0.99})
    assert r_crit.effective_risk == "CRITICAL"
    assert r_crit.decision == GovernanceDecision.REJECT


# ---------------------------------------------------------------------------
# Lifecycle State Transitions & Modification Tests
# ---------------------------------------------------------------------------

def test_approve_and_reject_actions(governance_svc):
    """Verify human supervisor approve and reject flows."""
    action = {
        "action": "MODIFY_PRODUCTION_SCENE",
        "reason": "Update texture path",
        "risk": "HIGH",
        "confidence": 0.88,
    }
    approval = governance_svc.create_approval_request(action=action, incident_id="inc-004")
    assert approval.status == ApprovalStatus.PENDING

    # Approve
    approved = governance_svc.approve_action(
        approval_id=approval.approval_id,
        actor="lead_lighting_td",
        notes="Approved after checking color fidelity",
    )
    assert approved.status == ApprovalStatus.APPROVED
    assert approved.approved_by == "lead_lighting_td"

    # Cannot re-approve already decided action
    with pytest.raises(ValueError, match="Cannot approve"):
        governance_svc.approve_action(approval_id=approval.approval_id, actor="another_td")


def test_modify_action_reevaluates_policy(governance_svc):
    """
    Modifying an action updates its parameters/risk and triggers automatic
    policy re-evaluation.
    """
    action = {
        "action": "RETRY_JOB",
        "reason": "Retry on 80GB GPU node",
        "risk": "HIGH",  # High because of expensive pool
        "confidence": 0.95,
        "parameters": {"pool": "80gb_vram_nodes"},
    }
    approval = governance_svc.create_approval_request(action=action, incident_id="inc-005")
    assert approval.status == ApprovalStatus.PENDING

    # Supervisor modifies to use standard 48GB GPU pool with LOW risk
    modified = governance_svc.modify_action(
        approval_id=approval.approval_id,
        actor="render_wrangler_lead",
        updated_parameters={"pool": "standard_48gb_nodes"},
        updated_risk="LOW",
        reason="Changed target pool to standard queue",
    )
    
    assert modified.status == ApprovalStatus.AUTO_APPROVED
    assert modified.action["parameters"]["pool"] == "standard_48gb_nodes"
    assert modified.action["risk"] == "LOW"
    assert len(modified.modification_history) == 1
    assert modified.modification_history[0]["actor"] == "render_wrangler_lead"


def test_immutable_audit_record_creation(governance_svc):
    """
    Every governance action (creation, auto-approval, human approval, modification, rejection)
    must produce an immutable audit log entry.
    """
    initial_count = len(governance_svc.get_audit_records())

    # 1. Create PENDING
    action = {"action": "ASSIGN_PIPELINE_TD", "confidence": 0.85, "risk": "MEDIUM"}
    app_req = governance_svc.create_approval_request(action=action, incident_id="inc-006")
    
    # 2. Modify
    governance_svc.modify_action(
        approval_id=app_req.approval_id,
        actor="supervisor_td",
        updated_parameters={"assigned_to": "alice_td"},
        reason="Assign specifically to shading lead",
    )

    # 3. Approve
    governance_svc.approve_action(
        approval_id=app_req.approval_id,
        actor="head_of_pipeline",
        notes="Approved ticket assignment",
    )

    audit_records = governance_svc.get_audit_records()
    assert len(audit_records) >= initial_count + 3
    
    actions = [rec["action"] for rec in audit_records]
    assert "CREATED_PENDING" in actions
    assert "MODIFIED" in actions
    assert "APPROVED" in actions


# ---------------------------------------------------------------------------
# REST API Endpoints Tests
# ---------------------------------------------------------------------------

def test_api_list_and_get_approvals(client, governance_svc):
    """Test GET /api/v1/approvals and GET /api/v1/approvals/{id}"""
    # Create test requests
    req1 = governance_svc.create_approval_request(
        action={"action": "RETRY_JOB", "confidence": 0.95, "risk": "LOW"},
        incident_id="inc-api-1",
    )
    req2 = governance_svc.create_approval_request(
        action={"action": "MODIFY_PRODUCTION_SCENE", "confidence": 0.85, "risk": "HIGH"},
        incident_id="inc-api-2",
    )

    # List all
    res = client.get("/api/v1/approvals")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 2

    # Filter by status
    res_pending = client.get("/api/v1/approvals?status=PENDING")
    assert res_pending.status_code == 200
    pending_data = res_pending.json()
    assert any(item["approval_id"] == req2.approval_id for item in pending_data["approvals"])

    # Get by ID
    res_single = client.get(f"/api/v1/approvals/{req2.approval_id}")
    assert res_single.status_code == 200
    assert res_single.json()["approval_id"] == req2.approval_id

    # 404 for nonexistent
    res_404 = client.get("/api/v1/approvals/non-existent-id")
    assert res_404.status_code == 404


def test_api_approve_and_reject_endpoints(client, governance_svc):
    """Test POST /api/v1/approvals/{id}/approve and /reject"""
    req = governance_svc.create_approval_request(
        action={"action": "RESTART_RENDER_DAEMON", "confidence": 0.80, "risk": "MEDIUM"},
        incident_id="inc-api-3",
    )

    # Approve
    approve_payload = {"actor": "system_admin", "notes": "Service verified offline, approving restart."}
    res_app = client.post(f"/api/v1/approvals/{req.approval_id}/approve", json=approve_payload)
    assert res_app.status_code == 200
    assert res_app.json()["status"] == "APPROVED"
    assert res_app.json()["approved_by"] == "system_admin"

    # Create another request to test reject
    req_rej = governance_svc.create_approval_request(
        action={"action": "DELETE_ASSET", "confidence": 0.80, "risk": "HIGH"},
        incident_id="inc-api-4",
    )

    reject_payload = {"actor": "vfx_supervisor", "notes": "Do not delete; shot is still being comped."}
    res_rej = client.post(f"/api/v1/approvals/{req_rej.approval_id}/reject", json=reject_payload)
    assert res_rej.status_code == 200
    assert res_rej.json()["status"] == "REJECTED"
