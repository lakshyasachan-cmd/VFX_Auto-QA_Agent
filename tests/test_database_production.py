"""
Unit & integration tests for production models (Projects, Sequences, Shots, RenderJobs, RenderNodes).
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.database.repositories.production_repo import (
    ProjectRepository,
    RenderJobRepository,
    RenderNodeRepository,
    SequenceRepository,
    ShotRepository,
)


@pytest.fixture
def db_session():
    test_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(bind=test_engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=test_engine)


def test_project_crud(db_session):
    repo = ProjectRepository(db_session)
    proj = repo.create(name="Dune 3", code="DUNE3", description="Epic Sci-Fi")
    assert proj.id is not None
    assert proj.code == "DUNE3"

    fetched = repo.get_by_code("DUNE3")
    assert fetched is not None
    assert fetched.name == "Dune 3"

    updated = repo.update(proj.id, status="archived")
    assert updated.status == "archived"


def test_sequence_and_shot_hierarchy(db_session):
    p_repo = ProjectRepository(db_session)
    seq_repo = SequenceRepository(db_session)
    shot_repo = ShotRepository(db_session)

    proj = p_repo.create(name="Project Avatar", code="AVTR")
    seq = seq_repo.create(project_id=proj.id, code="SQ010", description="Opening scene")
    shot = shot_repo.create(
        project_id=proj.id,
        sequence_id=seq.id,
        code="SH001",
        status="in_progress",
        frame_start=1001,
        frame_end=1120,
    )

    assert seq.id is not None
    assert shot.id is not None
    assert shot.sequence_id == seq.id
    assert shot.project_id == proj.id

    shots = shot_repo.list_by_project(proj.id)
    assert len(shots) == 1
    assert shots[0].code == "SH001"


def test_render_node_and_job(db_session):
    p_repo = ProjectRepository(db_session)
    node_repo = RenderNodeRepository(db_session)
    job_repo = RenderJobRepository(db_session)

    proj = p_repo.create(name="Cyberpunk", code="CYBER")
    node = node_repo.create(
        node_id="render-node-42",
        gpu_model="RTX 4090",
        gpu_memory_gb=24.0,
        ram_gb=128.0,
        health_score=1.0,
    )
    job = job_repo.create(
        job_id="job_9981",
        project_id=proj.id,
        node_id=node.id,
        renderer="arnold",
        status="rendering",
    )

    assert node.node_id == "render-node-42"
    assert job.node_id == node.id

    # Update node health and status
    updated_node = node_repo.update_health("render-node-42", health_score=0.2, status="degraded")
    assert updated_node.health_score == 0.2
    assert updated_node.status == "degraded"
