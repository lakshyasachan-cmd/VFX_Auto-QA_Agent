"""
Repository for immutable AuditLogs.
"""

from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.audit import AuditLog
from backend.database.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, session: Session):
        super().__init__(AuditLog, session)

    def log(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        actor: str,
        previous_state: Optional[dict[str, Any]] = None,
        new_state: Optional[dict[str, Any]] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> AuditLog:
        """Create and commit an immutable audit record."""
        entry = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor=actor,
            previous_state=previous_state,
            new_state=new_state,
            details=details or {},
        )
        self.session.add(entry)
        self.session.commit()
        self.session.refresh(entry)
        return entry

    def list_by_entity(self, entity_type: str, entity_id: str) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
            .order_by(AuditLog.timestamp.desc())
        )
        return list(self.session.scalars(stmt).all())

    def list_recent(self, limit: int = 100) -> list[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
        return list(self.session.scalars(stmt).all())
