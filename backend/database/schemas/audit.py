"""
Pydantic boundary models for AuditLogs and complete Traceability lineage.
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.database.schemas.agent import AgentFindingRead, AgentRunRead, ReasoningResultRead
from backend.database.schemas.incident import IncidentEvidenceRead, IncidentRead
from backend.database.schemas.remediation import ActionRead, ApprovalRequestRead, RemediationPlanRead


class AuditLogBase(BaseModel):
    entity_type: str = Field(..., max_length=64)
    entity_id: str = Field(..., max_length=36)
    action: str = Field(..., max_length=64)
    actor: str = Field(..., max_length=128)
    previous_state: Optional[dict[str, Any]] = None
    new_state: Optional[dict[str, Any]] = None
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime


class AuditLogCreate(AuditLogBase):
    pass


class AuditLogRead(AuditLogBase):
    model_config = ConfigDict(from_attributes=True)

    id: str


class RemediationPlanTrace(RemediationPlanRead):
    approvals: list[ApprovalRequestRead] = Field(default_factory=list)
    actions: list[ActionRead] = Field(default_factory=list)


class ReasoningResultTrace(ReasoningResultRead):
    plans: list[RemediationPlanTrace] = Field(default_factory=list)


class AgentRunTrace(AgentRunRead):
    findings: list[AgentFindingRead] = Field(default_factory=list)


class IncidentTrace(BaseModel):
    """
    Complete end-to-end AI Decision Traceability graph:
    Incident
      -> Agent Runs (iterations)
         -> Findings
      -> Evidence
      -> Reasoning Results
         -> Remediation Plans
            -> Approvals
            -> Actions
      -> Audit Logs
    """
    model_config = ConfigDict(from_attributes=True)

    incident: IncidentRead
    evidence: list[IncidentEvidenceRead] = Field(default_factory=list)
    agent_runs: list[AgentRunTrace] = Field(default_factory=list)
    reasoning_results: list[ReasoningResultTrace] = Field(default_factory=list)
    audit_history: list[AuditLogRead] = Field(default_factory=list)
