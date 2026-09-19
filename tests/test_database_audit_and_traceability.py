"""
End-to-End Traceability and Audit Trail Verification.
Verifies the complete lineage:
incident
→ agent run
→ evidence
→ reasoning result
→ remediation plan
→ approval
→ executed action
→ audit log
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.database.repositories.agent_repo import (
    AgentFindingRepository,
    AgentRunRepository,
    ReasoningResultRepository,
)
from backend.database.repositories.audit_repo import AuditLogRepository
from backend.database.repositories.incident_repo import (
    IncidentEvidenceRepository,
    IncidentRepository,
)
from backend.database.repositories.remediation_repo import (
    ActionRepository,
    ApprovalRequestRepository,
    RemediationPlanRepository,
)
from backend.database.schemas.audit import IncidentTrace
from backend.database.services.traceability_service import TraceabilityService


@pytest.fixture
def db_session():
    test_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(bind=test_engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=test_engine)


def test_full_traceability_lineage(db_session):
    # Initialize all repositories
    inc_repo = IncidentRepository(db_session)
    ev_repo = IncidentEvidenceRepository(db_session)
    run_repo = AgentRunRepository(db_session)
    finding_repo = AgentFindingRepository(db_session)
    reasoning_repo = ReasoningResultRepository(db_session)
    plan_repo = RemediationPlanRepository(db_session)
    app_repo = ApprovalRequestRepository(db_session)
    act_repo = ActionRepository(db_session)
    audit_repo = AuditLogRepository(db_session)

    # 1. Incident Creation
    incident = inc_repo.create(
        correlation_id="corr-trace-001",
        title="Arnold Render Failure on Shot SH010",
        description="Texture cache out of memory on frame 1050",
        severity="HIGH",
        status="OPEN",
        event_type="RENDER_JOB_FAILED",
        source_system="deadline",
    )
    audit_repo.log(
        entity_type="Incident",
        entity_id=incident.id,
        action="CREATED",
        actor="vfx_event_ingestion",
        details={"source": "deadline", "event_type": "RENDER_JOB_FAILED"},
    )

    # 2. Evidence Captured
    evidence = ev_repo.create(
        incident_id=incident.id,
        evidence_type="RENDER_LOG",
        source="deadline",
        title="Deadline stderr snippet",
        raw_content="[arnold] fatal error: out of memory allocating 8GB image buffer",
        structured_data={"vram_mb": 24576, "required_mb": 32000},
        captured_at=datetime.now(timezone.utc),
    )

    # 3. Agent Runs (Multiple iterations)
    # Run A: Specialist Render QA
    run_qa = run_repo.create(
        incident_id=incident.id,
        agent_name="RenderQAAgent",
        agent_type="SPECIALIST",
        status="COMPLETED",
        iteration=1,
        started_at=datetime.now(timezone.utc),
        prompt_tokens=450,
        completion_tokens=180,
    )

    # Finding linked to evidence
    finding_1 = finding_repo.create(
        agent_run_id=run_qa.id,
        evidence_id=evidence.id,
        finding_type="VRAM_EXCEEDED",
        severity="HIGH",
        confidence=0.98,
        title="Uncompressed EXR textures caused 32GB VRAM allocation spike",
        description="Render node has 24GB VRAM, job required 32GB.",
    )

    # Run B: Supervisor Agent (Synthesis)
    run_sup = run_repo.create(
        incident_id=incident.id,
        agent_name="IncidentSupervisor",
        agent_type="SUPERVISOR",
        status="COMPLETED",
        iteration=1,
        started_at=datetime.now(timezone.utc),
        prompt_tokens=800,
        completion_tokens=250,
    )

    # 4. Reasoning Result
    reasoning = reasoning_repo.create(
        incident_id=incident.id,
        agent_run_id=run_sup.id,
        root_cause="VRAM limit exceeded due to uncompressed 8K textures on a 24GB blade",
        confidence=0.98,
        summary="Render crashed at frame 1050 because scene geometry + 8K textures exceeded 24GB VRAM.",
        hypotheses_evaluated=[
            {"hypothesis": "Shader bug", "confidence": 0.05},
            {"hypothesis": "Texture memory spike", "confidence": 0.98},
        ],
        evidence_refs=[evidence.id],
    )

    # 5. Remediation Plan
    plan = plan_repo.create(
        incident_id=incident.id,
        reasoning_result_id=reasoning.id,
        strategy="Retry job on 48GB A6000 node pool and notify lighting lead",
        risk_level="MEDIUM",
        status="AWAITING_APPROVAL",
        requires_approval=True,
    )
    audit_repo.log(
        entity_type="RemediationPlan",
        entity_id=plan.id,
        action="PROPOSED",
        actor="remediation_strategy_agent",
        details={"incident_id": incident.id, "reasoning_id": reasoning.id},
    )

    # 6. Governance Approval Request
    approval = app_repo.create(
        plan_id=plan.id,
        status="PENDING",
        requested_at=datetime.now(timezone.utc),
        policy_evaluated={"requires_human_signoff": True},
    )

    # Lead TD approves
    decided_app = app_repo.decide(
        approval_id=approval.id,
        decision="APPROVED",
        decided_by="lead_td_alex",
        reason="Verified node pool capacity available",
    )
    audit_repo.log(
        entity_type="ApprovalRequest",
        entity_id=approval.id,
        action="APPROVED",
        actor="lead_td_alex",
        details={"decision": "APPROVED", "plan_id": plan.id},
    )

    # 7. Executed Action
    action = act_repo.create(
        plan_id=plan.id,
        action_type="RETRY_JOB",
        tool_name="retry_job_on_healthy_node",
        parameters={"job_id": "job_1050", "excluded_nodes": ["blade-01"]},
        execution_order=1,
    )
    act_repo.update_execution(
        action_id=action.id,
        status="COMPLETED",
        result_payload={"new_job_id": "job_1050_retry_1", "assigned_node": "blade-a6000-05"},
    )
    audit_repo.log(
        entity_type="Action",
        entity_id=action.id,
        action="EXECUTED",
        actor="mcp_watsonx_orchestrator",
        details={"result": "new_job_id: job_1050_retry_1"},
    )

    # 8. Query Complete Trace using TraceabilityService
    trace_service = TraceabilityService(db_session)
    trace = trace_service.get_incident_trace(incident.id)

    assert trace is not None
    assert isinstance(trace, IncidentTrace)

    # Trace Lineage Validations:
    # A. Incident
    assert trace.incident.id == incident.id
    assert trace.incident.title == "Arnold Render Failure on Shot SH010"

    # B. Evidence
    assert len(trace.evidence) == 1
    assert trace.evidence[0].id == evidence.id
    assert trace.evidence[0].evidence_type == "RENDER_LOG"

    # C. Agent Runs & Multiple runs support
    assert len(trace.agent_runs) == 2
    assert trace.agent_runs[0].agent_name == "RenderQAAgent"
    assert len(trace.agent_runs[0].findings) == 1
    assert trace.agent_runs[0].findings[0].evidence_id == evidence.id

    # D. Reasoning Results
    assert len(trace.reasoning_results) == 1
    rr = trace.reasoning_results[0]
    assert rr.id == reasoning.id
    assert "8K textures" in rr.root_cause
    assert rr.confidence == 0.98

    # E. Remediation Plan -> Approvals -> Actions
    assert len(rr.plans) == 1
    p = rr.plans[0]
    assert p.id == plan.id
    assert len(p.approvals) == 1
    assert p.approvals[0].status == "APPROVED"
    assert p.approvals[0].decided_by == "lead_td_alex"

    assert len(p.actions) == 1
    act = p.actions[0]
    assert act.tool_name == "retry_job_on_healthy_node"
    assert act.status == "COMPLETED"
    assert act.result_payload["new_job_id"] == "job_1050_retry_1"

    # F. Complete Audit History
    assert len(trace.audit_history) >= 1
    assert trace.audit_history[0].entity_id == incident.id
    assert trace.audit_history[0].action == "CREATED"
