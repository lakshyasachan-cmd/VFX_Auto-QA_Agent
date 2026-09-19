"""
Pydantic boundary models for RemediationPlans, ApprovalRequests, and Actions.
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class ActionBase(BaseModel):
    plan_id: str
    action_type: str = Field(..., max_length=64)
    tool_name: str = Field(..., max_length=64)
    parameters: dict[str, Any] = Field(default_factory=dict)
    execution_order: int = Field(default=1, ge=1)
    is_reversible: bool = True
    status: str = Field(default="PENDING", max_length=32)
    result_payload: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    executed_at: Optional[datetime] = None


class ActionCreate(ActionBase):
    pass


class ActionRead(ActionBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class ApprovalRequestBase(BaseModel):
    plan_id: str
    status: str = Field(default="PENDING", max_length=32)
    requested_at: datetime
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    decision_reason: Optional[str] = None
    policy_evaluated: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequestCreate(ApprovalRequestBase):
    pass


class ApprovalDecision(BaseModel):
    decision: str = Field(..., description="APPROVED or REJECTED")
    decided_by: str
    decision_reason: Optional[str] = None


class ApprovalRequestRead(ApprovalRequestBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class RemediationPlanBase(BaseModel):
    incident_id: str
    reasoning_result_id: Optional[str] = None
    strategy: str
    risk_level: str = Field(default="MEDIUM", max_length=32)
    status: str = Field(default="PROPOSED", max_length=32)
    requires_approval: bool = True
    rollback_strategy: Optional[str] = None
    preventive_measures: list[str] = Field(default_factory=list)


class RemediationPlanCreate(RemediationPlanBase):
    pass


class RemediationPlanRead(RemediationPlanBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
