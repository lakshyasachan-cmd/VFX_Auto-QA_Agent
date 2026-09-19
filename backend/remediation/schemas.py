"""
Pydantic schemas for the Remediation Strategy Specialist.
Defines structured remediation action proposals, risk classifications, and plan proposals.
"""

from enum import Enum
import uuid
from typing import Any, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class ActionType(str, Enum):
    RETRY_JOB = "RETRY_JOB"
    ASSIGN_PIPELINE_TD = "ASSIGN_PIPELINE_TD"
    UPDATE_SHOT_STATUS = "UPDATE_SHOT_STATUS"
    CREATE_INCIDENT = "CREATE_INCIDENT"
    NOTIFY_TEAM = "NOTIFY_TEAM"
    GENERATE_POSTMORTEM = "GENERATE_POSTMORTEM"
    NO_ACTION = "NO_ACTION"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RemediationActionProposal(BaseModel):
    """
    Standard proposed action item required by the specification:
    {
      "action": "...",
      "reason": "...",
      "risk": "...",
      "confidence": 0.0,
      "requires_human_approval": true,
      "parameters": {...}
    }
    """
    model_config = ConfigDict(extra="ignore")

    action: str = Field(..., description="Action name (e.g. RETRY_JOB, ASSIGN_PIPELINE_TD)")
    reason: str = Field(..., description="Justification grounded in root-cause findings")
    risk: str = Field(..., description="Deterministic risk level: LOW, MEDIUM, HIGH, CRITICAL")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in action suitability")
    requires_human_approval: bool = Field(default=True, description="Enforced by deterministic policy")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Execution parameters for downstream MCP client")


class RemediationPlanProposal(BaseModel):
    """Structured remediation plan containing sequenced action proposals."""
    model_config = ConfigDict(extra="ignore")

    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    root_cause: str
    strategy_summary: str
    overall_risk: str = "MEDIUM"
    requires_human_approval: bool = True
    actions: list[RemediationActionProposal] = Field(default_factory=list)
    rollback_plan: Optional[str] = None
    policy_evaluation_log: list[str] = Field(default_factory=list)


class RemediationInputContext(BaseModel):
    """Input payload to generate a remediation plan."""
    model_config = ConfigDict(extra="ignore")

    root_cause_analysis: Union[dict[str, Any], Any] = Field(..., description="Root cause reasoning output")
    evidence: list[str] = Field(default_factory=list, description="Aggregated specialist evidence")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    incident_severity: str = Field(default="MEDIUM", description="CRITICAL, HIGH, MEDIUM, LOW, INFO")
    incident_id: Optional[str] = None
    job_id: Optional[str] = None
    shot_id: Optional[str] = None
    node_id: Optional[str] = None
    project: Optional[str] = None
