"""
Repositories for VFX production hierarchy and compute nodes.
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.production import (
    Project,
    RenderJob,
    RenderNode,
    Sequence,
    Shot,
)
from backend.database.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    def __init__(self, session: Session):
        super().__init__(Project, session)

    def get_by_code(self, code: str) -> Optional[Project]:
        stmt = select(Project).where(Project.code == code)
        return self.session.scalars(stmt).first()


class SequenceRepository(BaseRepository[Sequence]):
    def __init__(self, session: Session):
        super().__init__(Sequence, session)

    def list_by_project(self, project_id: str) -> list[Sequence]:
        stmt = select(Sequence).where(Sequence.project_id == project_id)
        return list(self.session.scalars(stmt).all())


class ShotRepository(BaseRepository[Shot]):
    def __init__(self, session: Session):
        super().__init__(Shot, session)

    def get_by_code(self, project_id: str, code: str) -> Optional[Shot]:
        stmt = select(Shot).where(Shot.project_id == project_id, Shot.code == code)
        return self.session.scalars(stmt).first()

    def list_by_project(self, project_id: str) -> list[Shot]:
        stmt = select(Shot).where(Shot.project_id == project_id)
        return list(self.session.scalars(stmt).all())


class RenderNodeRepository(BaseRepository[RenderNode]):
    def __init__(self, session: Session):
        super().__init__(RenderNode, session)

    def get_by_node_id(self, node_id: str) -> Optional[RenderNode]:
        stmt = select(RenderNode).where(RenderNode.node_id == node_id)
        return self.session.scalars(stmt).first()

    def update_health(self, node_id: str, health_score: float, status: str = "online") -> Optional[RenderNode]:
        node = self.get_by_node_id(node_id)
        if node:
            node.health_score = health_score
            node.status = status
            self.session.commit()
            self.session.refresh(node)
        return node


class RenderJobRepository(BaseRepository[RenderJob]):
    def __init__(self, session: Session):
        super().__init__(RenderJob, session)

    def get_by_job_id(self, job_id: str) -> Optional[RenderJob]:
        stmt = select(RenderJob).where(RenderJob.job_id == job_id)
        return self.session.scalars(stmt).first()

    def update_status(self, job_id: str, status: str) -> Optional[RenderJob]:
        job = self.get_by_job_id(job_id)
        if job:
            job.status = status
            self.session.commit()
            self.session.refresh(job)
        return job
