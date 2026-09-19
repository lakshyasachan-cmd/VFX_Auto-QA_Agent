"""
Pydantic boundary models for AgentRuns, AgentFindings, and ReasoningResults.
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class AgentFindingBase(BaseModel):
    agent_run_id: str
    evidence_id: Optional[str] = None
    finding_type: str = Field(..., max_length=64)
    severity: str = Field(default="MEDIUM", max_length=32)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    title: str = Field(..., max_length=256)
    description: Optional[str] = None
    structured_payload: dict[str, Any] = Field(default_factory=dict)


class AgentFindingCreate(AgentFindingBase):
    pass


class AgentFindingRead(AgentFindingBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class AgentRunBase(BaseModel):
    incident_id: str
    agent_name: str = Field(..., max_length=64)
    agent_type: str = Field(..., max_length=64)
    status: str = Field(default="RUNNING", max_length=32)
    iteration: int = Field(default=1, ge=1)
    started_at: datetime
    completed_at: Optional[datetime] = None
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    error_message: Optional[str] = None
    input_context: dict[str, Any] = Field(default_factory=dict)
    output_summary: Optional[str] = None


class AgentRunCreate(AgentRunBase):
    pass


class AgentRunRead(AgentRunBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class ReasoningResultBase(BaseModel):
    incident_id: str
    agent_run_id: Optional[str] = None
    root_cause: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    summary: str
    hypotheses_evaluated: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class ReasoningResultCreate(ReasoningResultBase):
    pass


class ReasoningResultRead(ReasoningResultBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
