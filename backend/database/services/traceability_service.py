"""
Service assembling the complete end-to-end AI Decision Traceability graph:
incident
→ agent run
→ evidence
→ reasoning result
→ remediation plan
→ approval
→ executed action
→ audit log
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.database.models.audit import AuditLog
from backend.database.models.incident import Incident
from backend.database.schemas.agent import AgentFindingRead, AgentRunRead, ReasoningResultRead
from backend.database.schemas.audit import (
    AgentRunTrace,
    AuditLogRead,
    IncidentTrace,
    ReasoningResultTrace,
    RemediationPlanTrace,
)
from backend.database.schemas.incident import IncidentEvidenceRead, IncidentRead
from backend.database.schemas.remediation import ActionRead, ApprovalRequestRead


class TraceabilityService:
    """Service to load and build the complete traceability graph for an incident."""

    def __init__(self, session: Session):
        self.session = session

    def get_incident_trace(self, incident_id: str) -> Optional[IncidentTrace]:
        """
        Builds the complete immutable audit graph for an incident.
        """
        stmt = (
            select(Incident)
            .where(Incident.id == incident_id)
            .options(
                selectinload(Incident.evidence),
                selectinload(Incident.agent_runs),
                selectinload(Incident.reasoning_results),
                selectinload(Incident.remediation_plans),
            )
        )
        incident_model = self.session.scalars(stmt).first()
        if not incident_model:
            return None

        # 1. Incident
        incident_dto = IncidentRead.model_validate(incident_model)

        # 2. Evidence
        evidence_dtos = [
            IncidentEvidenceRead.model_validate(ev) for ev in incident_model.evidence
        ]

        # 3. Agent Runs (with findings for each run)
        agent_run_traces = []
        for run in incident_model.agent_runs:
            findings_dtos = [AgentFindingRead.model_validate(f) for f in run.findings]
            run_dto = AgentRunRead.model_validate(run)
            agent_run_traces.append(
                AgentRunTrace(
                    **run_dto.model_dump(),
                    findings=findings_dtos,
                )
            )

        # 4. Reasoning Results (with plans -> approvals -> actions)
        reasoning_traces = []
        for reasoning in incident_model.reasoning_results:
            reasoning_dto = ReasoningResultRead.model_validate(reasoning)

            # Plans attached to this reasoning result
            plans_for_reasoning = [
                p for p in incident_model.remediation_plans if p.reasoning_result_id == reasoning.id
            ]
            plan_traces = []
            for plan in plans_for_reasoning:
                approvals = [ApprovalRequestRead.model_validate(app) for app in plan.approval_requests]
                actions = [ActionRead.model_validate(act) for act in plan.actions]
                plan_dto = RemediationPlanTrace(
                    id=plan.id,
                    incident_id=plan.incident_id,
                    reasoning_result_id=plan.reasoning_result_id,
                    strategy=plan.strategy,
                    risk_level=plan.risk_level,
                    status=plan.status,
                    requires_approval=plan.requires_approval,
                    rollback_strategy=plan.rollback_strategy,
                    preventive_measures=plan.preventive_measures,
                    created_at=plan.created_at,
                    updated_at=plan.updated_at,
                    approvals=approvals,
                    actions=actions,
                )
                plan_traces.append(plan_dto)

            reasoning_traces.append(
                ReasoningResultTrace(
                    **reasoning_dto.model_dump(),
                    plans=plan_traces,
                )
            )

        # 5. Audit History
        audit_stmt = (
            select(AuditLog)
            .where(AuditLog.entity_id == incident_id)
            .order_by(AuditLog.timestamp.asc())
        )
        audit_records = list(self.session.scalars(audit_stmt).all())
        audit_dtos = [AuditLogRead.model_validate(a) for a in audit_records]

        return IncidentTrace(
            incident=incident_dto,
            evidence=evidence_dtos,
            agent_runs=agent_run_traces,
            reasoning_results=reasoning_traces,
            audit_history=audit_dtos,
        )
