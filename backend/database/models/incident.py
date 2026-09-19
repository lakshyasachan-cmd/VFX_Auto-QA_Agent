"""
SQLAlchemy 2.x models for Incidents and IncidentEvidence.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, TimestampMixin, generate_uuid_str

if TYPE_CHECKING:
    from backend.database.models.agent import AgentFinding, AgentRun, ReasoningResult
    from backend.database.models.production import Project, RenderJob, RenderNode, Shot
    from backend.database.models.remediation import RemediationPlan


class Incident(Base, TimestampMixin):
    """Central Aggregate Incident record."""
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid_str)
    correlation_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(32), default="MEDIUM", index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_system: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    # Optional Production Entity links
    project_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), index=True, nullable=True)
    shot_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("shots.id", ondelete="SET NULL"), index=True, nullable=True)
    render_job_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("render_jobs.id", ondelete="SET NULL"), index=True, nullable=True)
    render_node_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("render_nodes.id", ondelete="SET NULL"), index=True, nullable=True)

    # Error fingerprint for deduplication & pattern recognition
    error_signature: Mapped[Optional[str]] = mapped_column(String(256), index=True, nullable=True)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Relationships to Production
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="incidents")
    shot: Mapped[Optional["Shot"]] = relationship("Shot", back_populates="incidents")
    render_job: Mapped[Optional["RenderJob"]] = relationship("RenderJob", back_populates="incidents")
    render_node: Mapped[Optional["RenderNode"]] = relationship("RenderNode", back_populates="incidents")

    # Investigation & Traceability Lineage
    evidence: Mapped[list["IncidentEvidence"]] = relationship(
        "IncidentEvidence",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentEvidence.created_at",
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship(
        "AgentRun",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="AgentRun.iteration",
    )
    reasoning_results: Mapped[list["ReasoningResult"]] = relationship(
        "ReasoningResult",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="ReasoningResult.created_at",
    )
    remediation_plans: Mapped[list["RemediationPlan"]] = relationship(
        "RemediationPlan",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="RemediationPlan.created_at",
    )


class IncidentEvidence(Base, TimestampMixin):
    """Raw or structured telemetry, logs, or diagnostics attached to an incident."""
    __tablename__ = "incident_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid_str)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # RENDER_LOG, NODE_TELEMETRY, USD_STAGE, FRAME_QC
    source: Mapped[str] = mapped_column(String(64), nullable=False)  # deadline, tractor, opencue, asset_storage
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # log snippet, stack trace
    structured_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # parsed metrics, json
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    incident: Mapped["Incident"] = relationship("Incident", back_populates="evidence")
    findings: Mapped[list["AgentFinding"]] = relationship("AgentFinding", back_populates="evidence")
