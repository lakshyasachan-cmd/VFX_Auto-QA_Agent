"""
Pydantic boundary models for Incidents and IncidentEvidence.
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class IncidentEvidenceBase(BaseModel):
    incident_id: str
    evidence_type: str = Field(..., max_length=64)
    source: str = Field(..., max_length=64)
    title: str = Field(..., max_length=256)
    raw_content: Optional[str] = None
    structured_data: dict[str, Any] = Field(default_factory=dict)
    captured_at: datetime


class IncidentEvidenceCreate(IncidentEvidenceBase):
    pass


class IncidentEvidenceRead(IncidentEvidenceBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class IncidentBase(BaseModel):
    correlation_id: str
    title: str = Field(..., max_length=256)
    description: Optional[str] = None
    severity: str = Field(default="MEDIUM", max_length=32)
    status: str = Field(default="OPEN", max_length=32)
    event_type: str = Field(..., max_length=64)
    source_system: str = Field(..., max_length=64)
    project_id: Optional[str] = None
    shot_id: Optional[str] = None
    render_job_id: Optional[str] = None
    render_node_id: Optional[str] = None
    error_signature: Optional[str] = None
    assigned_to: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_summary: Optional[str] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class IncidentCreate(IncidentBase):
    pass


class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_summary: Optional[str] = None
    metadata_json: Optional[dict[str, Any]] = None


class IncidentRead(IncidentBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
