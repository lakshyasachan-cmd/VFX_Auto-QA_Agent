"""
Repositories for Incidents and IncidentEvidence.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.database.models.incident import Incident, IncidentEvidence
from backend.database.repositories.base import BaseRepository


class IncidentRepository(BaseRepository[Incident]):
    def __init__(self, session: Session):
        super().__init__(Incident, session)

    def get_by_correlation_id(self, correlation_id: str) -> list[Incident]:
        stmt = select(Incident).where(Incident.correlation_id == correlation_id)
        return list(self.session.scalars(stmt).all())

    def get_with_relations(self, incident_id: str) -> Optional[Incident]:
        """Fetch incident with all related evidence, agent runs, and reasoning eager-loaded."""
        stmt = (
            select(Incident)
            .where(Incident.id == incident_id)
            .options(
                selectinload(Incident.evidence),
                selectinload(Incident.agent_runs),
                selectinload(Incident.reasoning_results),
                selectinload(Incident.remediation_plans),
            )
        )
        return self.session.scalars(stmt).first()

    def list_filtered(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Incident]:
        stmt = select(Incident)
        if status:
            stmt = stmt.where(Incident.status == status)
        if severity:
            stmt = stmt.where(Incident.severity == severity)
        if project_id:
            stmt = stmt.where(Incident.project_id == project_id)
        stmt = stmt.order_by(Incident.created_at.desc()).limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all())

    def update_status(self, incident_id: str, status: str, resolution_summary: Optional[str] = None) -> Optional[Incident]:
        incident = self.get_by_id(incident_id)
        if incident:
            incident.status = status
            if status in ("RESOLVED", "CLOSED"):
                incident.resolved_at = datetime.now(timezone.utc)
            if resolution_summary:
                incident.resolution_summary = resolution_summary
            self.session.commit()
            self.session.refresh(incident)
        return incident


class IncidentEvidenceRepository(BaseRepository[IncidentEvidence]):
    def __init__(self, session: Session):
        super().__init__(IncidentEvidence, session)

    def list_by_incident(self, incident_id: str) -> list[IncidentEvidence]:
        stmt = select(IncidentEvidence).where(IncidentEvidence.incident_id == incident_id).order_by(IncidentEvidence.captured_at)
        return list(self.session.scalars(stmt).all())
