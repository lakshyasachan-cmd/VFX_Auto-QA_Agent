"""
Unit & integration tests for RemediationPlans, ApprovalRequests, and Actions.
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.database.repositories.incident_repo import IncidentRepository
from backend.database.repositories.remediation_repo import (
    ActionRepository,
    ApprovalRequestRepository,
    RemediationPlanRepository,
)


@pytest.fixture
def db_session():
    test_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(bind=test_engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=test_engine)


def test_remediation_workflow(db_session):
    inc_repo = IncidentRepository(db_session)
    plan_repo = RemediationPlanRepository(db_session)
    app_repo = ApprovalRequestRepository(db_session)
    act_repo = ActionRepository(db_session)

    incident = inc_repo.create(
        correlation_id="corr-plan-1",
        title="OOM Failure on Job 101",
        severity="HIGH",
        status="REMEDIATING",
        event_type="RENDER_JOB_FAILED",
        source_system="deadline",
    )

    # 1. Propose remediation plan
    plan = plan_repo.create(
        incident_id=incident.id,
        strategy="Quarantine degraded blade, retry render job on high-VRAM pool, notify lighting artist",
        risk_level="MEDIUM",
        status="AWAITING_APPROVAL",
        requires_approval=True,
        preventive_measures=["Lower texture mipmap budget", "Pre-flight memory check"],
    )
    assert plan.id is not None
    assert plan.status == "AWAITING_APPROVAL"

    # 2. Add ordered actions
    act1 = act_repo.create(
        plan_id=plan.id,
        action_type="RETRY_JOB",
        tool_name="retry_job_on_healthy_node",
        parameters={"job_id": "job_101", "excluded_nodes": ["render-node-42"]},
        execution_order=1,
    )
    act2 = act_repo.create(
        plan_id=plan.id,
        action_type="NOTIFY_TEAM",
        tool_name="notify_team",
        parameters={"channel": "#vfx-lighting-alerts", "message": "Job rerouted"},
        execution_order=2,
    )

    actions = act_repo.list_by_plan(plan.id)
    assert len(actions) == 2
    assert actions[0].execution_order == 1
    assert actions[1].execution_order == 2

    # 3. Create Approval Request
    approval = app_repo.create(
        plan_id=plan.id,
        status="PENDING",
        requested_at=datetime.now(timezone.utc),
        policy_evaluated={"requires_lead_signoff": True, "risk": "MEDIUM"},
    )
    pending_list = app_repo.list_pending()
    assert len(pending_list) == 1
    assert pending_list[0].id == approval.id

    # 4. Human-in-the-loop Lead TD approves
    decided = app_repo.decide(
        approval_id=approval.id,
        decision="APPROVED",
        decided_by="lead_td_sarah",
        reason="Approved re-routing to node pool B",
    )
    assert decided.status == "APPROVED"
    assert decided.decided_by == "lead_td_sarah"

    # 5. Execute Action
    act_repo.update_execution(
        action_id=act1.id,
        status="COMPLETED",
        result_payload={"new_job_id": "job_101_retry_1", "status": "queued"},
    )
    executed_act = act_repo.get_by_id(act1.id)
    assert executed_act.status == "COMPLETED"
    assert executed_act.result_payload["new_job_id"] == "job_101_retry_1"
