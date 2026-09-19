"""
Pydantic schemas and DTOs for the AI Governance & Deterministic Policy subsystem.
Defines approval request structures, governance decision outcomes, and REST request/response payloads.
"""

from enum import Enum
import uuid
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    AUTO_APPROVED = "AUTO_APPROVED"
    MODIFIED = "MODIFIED"


class GovernanceDecision(str, Enum):
    AUTO_APPROVE = "AUTO_APPROVE"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"
    POLICY_REJECT = "POLICY_REJECT"
    REJECT = "POLICY_REJECT"



class PolicyEvaluationResult(BaseModel):
    """Result of deterministic policy evaluation on a proposed action."""
    model_config = ConfigDict(extra="ignore")

    decision: GovernanceDecision
    risk: str = Field(..., description="LOW, MEDIUM, HIGH, CRITICAL")
    policy_rule: str
    reason: str
    is_blocked: bool = False
    audit_metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def effective_risk(self) -> str:
        return self.risk

    @property
    def requires_human_approval(self) -> bool:
        return self.decision == GovernanceDecision.HUMAN_APPROVAL

    @property
    def reasoning(self) -> str:
        return self.reason


class ApprovalRequestDTO(BaseModel):
    """Representation of an approval request record."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str
    action_name: str = Field(..., alias="action")
    status: str = ApprovalStatus.PENDING.value

    risk: str = "MEDIUM"
    confidence: float = 1.0
    requires_human_approval: bool = True
    parameters: dict[str, Any] = Field(default_factory=dict)
    requested_at: str
    decided_at: Optional[str] = None
    decided_by: Optional[str] = None
    decision_reason: Optional[str] = None
    policy_evaluated: dict[str, Any] = Field(default_factory=dict)
    modification_history: list[dict[str, Any]] = Field(default_factory=list)

    @computed_field
    @property
    def approval_id(self) -> str:
        return self.id

    @computed_field
    @property
    def approved_by(self) -> Optional[str]:
        if self.status in (ApprovalStatus.APPROVED.value, ApprovalStatus.AUTO_APPROVED.value):
            return self.decided_by
        return None

    @property
    def action(self) -> Any:
        return {
            "action": self.action_name,
            "parameters": self.parameters,
            "risk": self.risk,
            "confidence": self.confidence,
        }

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        data = super().model_dump(*args, **kwargs)
        data["approval_id"] = self.id
        data["approved_by"] = self.approved_by
        data["action"] = self.action_name
        return data


class DecisionRequest(BaseModel):
    """Payload to approve or reject a pending approval request."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    decided_by: Optional[str] = Field(None, description="Email or user ID of authorizer")
    reason: Optional[str] = Field(None, description="Justification for approval or rejection decision")
    actor: Optional[str] = Field(None, description="Alias for decided_by")
    notes: Optional[str] = Field(None, description="Alias for reason")

    def get_actor(self) -> str:
        return self.actor or self.decided_by or "human_supervisor"

    def get_reason(self) -> str:
        return self.notes or self.reason or "Decision submitted via governance API"


class ModifyActionRequest(BaseModel):
    """Payload to modify parameters of a pending approval request."""
    model_config = ConfigDict(extra="ignore")

    decided_by: str = Field(..., description="Email or user ID of modifier")
    modified_parameters: dict[str, Any] = Field(..., description="Updated parameter payload")
    reason: str = Field(..., description="Reason for parameter modification")


class ApprovalListResponse(BaseModel):
    """List of approval requests."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    total: int
    items: list[ApprovalRequestDTO] = Field(default_factory=list)
    approvals: list[ApprovalRequestDTO] = Field(default_factory=list)

    def __init__(self, **data: Any):
        if "approvals" in data and "items" not in data:
            data["items"] = data["approvals"]
        elif "items" in data and "approvals" not in data:
            data["approvals"] = data["items"]
        elif "items" in data and "approvals" in data:
            pass
        super().__init__(**data)
        if not self.approvals and self.items:
            self.approvals = self.items
        elif not self.items and self.approvals:
            self.items = self.approvals



