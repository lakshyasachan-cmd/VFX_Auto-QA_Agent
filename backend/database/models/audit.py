"""
SQLAlchemy 2.x model for immutable AuditLogs.
Tracks state changes, actors, and events across the entire platform.
"""

from datetime import datetime
from typing import Any, Optional
from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, generate_uuid_str, utc_now


class AuditLog(Base):
    """Immutable audit trail entry."""
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid_str)
    entity_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # Incident, RemediationPlan, etc.
    entity_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # CREATED, STATUS_CHANGED, APPROVED, EXECUTED
    actor: Mapped[str] = mapped_column(String(128), index=True, nullable=False)  # User, Agent, or Service name
    previous_state: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    new_state: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        index=True,
        nullable=False,
    )
