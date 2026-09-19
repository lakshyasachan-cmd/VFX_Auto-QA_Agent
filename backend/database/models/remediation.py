"""
SQLAlchemy 2.x models for RemediationPlans, ApprovalRequests, and Executable Actions.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, TimestampMixin, generate_uuid_str

if TYPE_CHECKING:
    from backend.database.models.agent import ReasoningResult
    from backend.database.models.incident import Incident


class RemediationPlan(Base, TimestampMixin):
    """Proposed remediation strategy synthesized from agent reasoning."""
    __tablename__ = "remediation_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid_str)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    reasoning_result_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("reasoning_results.id", ondelete="SET NULL"), index=True, nullable=True)
    strategy: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), default="MEDIUM", index=True, nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    status: Mapped[str] = mapped_column(String(32), default="PROPOSED", index=True, nullable=False)  # PROPOSED, AWAITING_APPROVAL, APPROVED, REJECTED, EXECUTED, FAILED
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rollback_strategy: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preventive_measures: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Relationships
    incident: Mapped["Incident"] = relationship("Incident", back_populates="remediation_plans")
    reasoning_result: Mapped[Optional["ReasoningResult"]] = relationship("ReasoningResult", back_populates="remediation_plans")
    approval_requests: Mapped[list["ApprovalRequest"]] = relationship(
        "ApprovalRequest",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="ApprovalRequest.created_at",
    )
    actions: Mapped[list["Action"]] = relationship(
        "Action",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="Action.execution_order",
    )


class ApprovalRequest(Base, TimestampMixin):
    """Governance checkpoint (Human-in-the-loop or Policy auto-approval)."""
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid_str)
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("remediation_plans.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True, nullable=False)  # PENDING, APPROVED, REJECTED, AUTO_APPROVED
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # User email/name or "policy_engine"
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    policy_evaluated: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Relationships
    plan: Mapped["RemediationPlan"] = relationship("RemediationPlan", back_populates="approval_requests")


class Action(Base, TimestampMixin):
    """Executable action or MCP tool invocation linked to an approved remediation plan."""
    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid_str)
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("remediation_plans.id", ondelete="CASCADE"), index=True, nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # RETRY_JOB, ASSIGN_TD, UPDATE_SHOT, NOTIFY
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)  # MCP tool name (e.g. retry_job_on_healthy_node)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    execution_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_reversible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True, nullable=False)  # PENDING, EXECUTING, COMPLETED, FAILED, SKIPPED
    result_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    plan: Mapped["RemediationPlan"] = relationship("RemediationPlan", back_populates="actions")
