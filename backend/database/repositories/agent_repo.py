"""
Repositories for AgentRuns, AgentFindings, and ReasoningResults.
Supports multiple agent runs per incident.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.database.models.agent import AgentFinding, AgentRun, ReasoningResult
from backend.database.repositories.base import BaseRepository


class AgentRunRepository(BaseRepository[AgentRun]):
    def __init__(self, session: Session):
        super().__init__(AgentRun, session)

    def list_by_incident(self, incident_id: str) -> list[AgentRun]:
        """Fetch all agent runs for an incident, supporting multiple runs & iterations."""
        stmt = (
            select(AgentRun)
            .where(AgentRun.incident_id == incident_id)
            .options(selectinload(AgentRun.findings))
            .order_by(AgentRun.iteration, AgentRun.started_at)
        )
        return list(self.session.scalars(stmt).all())

    def get_latest_iteration(self, incident_id: str, agent_name: str) -> int:
        stmt = (
            select(AgentRun.iteration)
            .where(AgentRun.incident_id == incident_id, AgentRun.agent_name == agent_name)
            .order_by(AgentRun.iteration.desc())
        )
        last_iter = self.session.scalars(stmt).first()
        return last_iter or 0

    def complete_run(
        self,
        run_id: str,
        output_summary: Optional[str] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> Optional[AgentRun]:
        run = self.get_by_id(run_id)
        if run:
            run.status = "COMPLETED"
            run.completed_at = datetime.now(timezone.utc)
            if output_summary:
                run.output_summary = output_summary
            run.prompt_tokens += prompt_tokens
            run.completion_tokens += completion_tokens
            self.session.commit()
            self.session.refresh(run)
        return run

    def fail_run(self, run_id: str, error_message: str) -> Optional[AgentRun]:
        run = self.get_by_id(run_id)
        if run:
            run.status = "FAILED"
            run.completed_at = datetime.now(timezone.utc)
            run.error_message = error_message
            self.session.commit()
            self.session.refresh(run)
        return run


class AgentFindingRepository(BaseRepository[AgentFinding]):
    def __init__(self, session: Session):
        super().__init__(AgentFinding, session)

    def list_by_run(self, agent_run_id: str) -> list[AgentFinding]:
        stmt = select(AgentFinding).where(AgentFinding.agent_run_id == agent_run_id)
        return list(self.session.scalars(stmt).all())


class ReasoningResultRepository(BaseRepository[ReasoningResult]):
    def __init__(self, session: Session):
        super().__init__(ReasoningResult, session)

    def list_by_incident(self, incident_id: str) -> list[ReasoningResult]:
        stmt = (
            select(ReasoningResult)
            .where(ReasoningResult.incident_id == incident_id)
            .order_by(ReasoningResult.created_at.desc())
        )
        return list(self.session.scalars(stmt).all())

    def get_latest_for_incident(self, incident_id: str) -> Optional[ReasoningResult]:
        stmt = (
            select(ReasoningResult)
            .where(ReasoningResult.incident_id == incident_id)
            .order_by(ReasoningResult.created_at.desc())
        )
        return self.session.scalars(stmt).first()
