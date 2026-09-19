"""
Pydantic boundary models for Production hierarchy (Projects, Sequences, Shots, Nodes, Jobs).
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class ProjectBase(BaseModel):
    name: str = Field(..., max_length=128)
    code: str = Field(..., max_length=64)
    status: str = Field(default="active", max_length=32)
    description: Optional[str] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ProjectCreate(ProjectBase):
    pass


class ProjectRead(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class SequenceBase(BaseModel):
    project_id: str
    code: str = Field(..., max_length=64)
    description: Optional[str] = None


class SequenceCreate(SequenceBase):
    pass


class SequenceRead(SequenceBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class ShotBase(BaseModel):
    project_id: str
    sequence_id: Optional[str] = None
    code: str = Field(..., max_length=64)
    status: str = Field(default="in_progress", max_length=32)
    frame_start: Optional[int] = None
    frame_end: Optional[int] = None
    assigned_lead: Optional[str] = None


class ShotCreate(ShotBase):
    pass


class ShotRead(ShotBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class RenderNodeBase(BaseModel):
    node_id: str = Field(..., max_length=128)
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    gpu_model: Optional[str] = None
    gpu_memory_gb: Optional[float] = None
    cpu_model: Optional[str] = None
    ram_gb: Optional[float] = None
    status: str = Field(default="online", max_length=32)
    health_score: float = Field(default=1.0, ge=0.0, le=1.0)
    last_heartbeat: Optional[datetime] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class RenderNodeCreate(RenderNodeBase):
    pass


class RenderNodeRead(RenderNodeBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class RenderJobBase(BaseModel):
    job_id: str = Field(..., max_length=128)
    project_id: Optional[str] = None
    shot_id: Optional[str] = None
    node_id: Optional[str] = None
    renderer: Optional[str] = None
    status: str = Field(default="queued", max_length=32)
    priority: int = Field(default=50)
    frame_range: Optional[str] = None
    submitted_by: Optional[str] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class RenderJobCreate(RenderJobBase):
    pass


class RenderJobRead(RenderJobBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
