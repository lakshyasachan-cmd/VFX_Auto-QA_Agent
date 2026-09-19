"""
Unit & integration tests for Incidents and IncidentEvidence.
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.database.repositories.incident_repo import (
    IncidentEvidenceRepository,
    IncidentRepository,
)
from backend.database.repositories.production_repo import (
    ProjectRepository,
    RenderNodeRepository,
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


def test_incident_and_evidence_lifecycle(db_session):
    p_repo = ProjectRepository(db_session)
    n_repo = RenderNodeRepository(db_session)
    inc_repo = IncidentRepository(db_session)
    ev_repo = IncidentEvidenceRepository(db_session)

    proj = p_repo.create(name="Matrix Resurrections", code="MTX")
    node = n_repo.create(node_id="blade-01", gpu_model="A6000")

    # Create Incident
    incident = inc_repo.create(
        correlation_id="corr-12345",
        title="Arnold GPU OOM on blade-01",
        description="Frame 1042 failed with CUDA out of memory",
        severity="HIGH",
        status="OPEN",
        event_type="RENDER_JOB_FAILED",
        source_system="deadline",
        project_id=proj.id,
        render_node_id=node.id,
        error_signature="GPU_OUT_OF_MEMORY:blade-01",
    )
    assert incident.id is not None
    assert incident.status == "OPEN"

    # Attach Evidence
    ev1 = ev_repo.create(
        incident_id=incident.id,
        evidence_type="RENDER_LOG",
        source="deadline",
        title="Arnold Crash Stack Trace",
        raw_content="[arnold] CUDA error: out of memory (24576MB allocated)",
        structured_data={"vram_used_mb": 24576, "exit_code": 137},
        captured_at=datetime.now(timezone.utc),
    )
    assert ev1.id is not None
    assert ev1.incident_id == incident.id

    evidence_list = ev_repo.list_by_incident(incident.id)
    assert len(evidence_list) == 1

    # Update status to RESOLVED
    updated = inc_repo.update_status(incident.id, "RESOLVED", "Re-rendered on 48GB A6000 node")
    assert updated.status == "RESOLVED"
    assert updated.resolved_at is not None
    assert updated.resolution_summary == "Re-rendered on 48GB A6000 node"
