"""
SQLAlchemy 2.x models for VFX production hierarchy and infrastructure.
Includes: Projects, Sequences, Shots, RenderJobs, RenderNodes.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, TimestampMixin, generate_uuid_str

if TYPE_CHECKING:
    from backend.database.models.incident import Incident


class Project(Base, TimestampMixin):
    """VFX Studio Production Project."""
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid_str)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Relationships
    sequences: Mapped[list["Sequence"]] = relationship("Sequence", back_populates="project", cascade="all, delete-orphan")
    shots: Mapped[list["Shot"]] = relationship("Shot", back_populates="project", cascade="all, delete-orphan")
    render_jobs: Mapped[list["RenderJob"]] = relationship("RenderJob", back_populates="project", cascade="all, delete-orphan")
    incidents: Mapped[list["Incident"]] = relationship("Incident", back_populates="project")


class Sequence(Base, TimestampMixin):
    """VFX Sequence container (e.g., SQ020)."""
    __tablename__ = "sequences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid_str)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="sequences")
    shots: Mapped[list["Shot"]] = relationship("Shot", back_populates="sequence", cascade="all, delete-orphan")


class Shot(Base, TimestampMixin):
    """VFX Shot (e.g., SH010)."""
    __tablename__ = "shots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid_str)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    sequence_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("sequences.id", ondelete="SET NULL"), index=True, nullable=True)
    code: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="in_progress", index=True, nullable=False)
    frame_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    frame_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    assigned_lead: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="shots")
    sequence: Mapped[Optional["Sequence"]] = relationship("Sequence", back_populates="shots")
    render_jobs: Mapped[list["RenderJob"]] = relationship("RenderJob", back_populates="shot", cascade="all, delete-orphan")
    incidents: Mapped[list["Incident"]] = relationship("Incident", back_populates="shot")


class RenderNode(Base, TimestampMixin):
    """Compute blade / worker machine on the render farm."""
    __tablename__ = "render_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid_str)
    node_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)  # e.g., "render-node-42"
    hostname: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    gpu_model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    gpu_memory_gb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cpu_model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    ram_gb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="online", index=True, nullable=False)  # online, offline, degraded, quarantined
    health_score: Mapped[float] = mapped_column(Float, default=1.0, index=True, nullable=False)  # 0.0 - 1.0
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Relationships
    render_jobs: Mapped[list["RenderJob"]] = relationship("RenderJob", back_populates="node")
    incidents: Mapped[list["Incident"]] = relationship("Incident", back_populates="render_node")


class RenderJob(Base, TimestampMixin):
    """Render farm job record from Deadline/Tractor/OpenCue."""
    __tablename__ = "render_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid_str)
    job_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)  # Farm job ID
    project_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), index=True, nullable=True)
    shot_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("shots.id", ondelete="SET NULL"), index=True, nullable=True)
    node_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("render_nodes.id", ondelete="SET NULL"), index=True, nullable=True)
    renderer: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # "arnold", "renderman", "vray"
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True, nullable=False)  # queued, rendering, completed, failed
    priority: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    frame_range: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    submitted_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Relationships
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="render_jobs")
    shot: Mapped[Optional["Shot"]] = relationship("Shot", back_populates="render_jobs")
    node: Mapped[Optional["RenderNode"]] = relationship("RenderNode", back_populates="render_jobs")
    incidents: Mapped[list["Incident"]] = relationship("Incident", back_populates="render_job")
