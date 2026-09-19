"""
Unit & integration tests for multi-agent execution persistence.
Verifies multiple agent runs per incident, granular findings, and synthesized reasoning results.
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.database.repositories.agent_repo import (
    AgentFindingRepository,
    AgentRunRepository,
    ReasoningResultRepository,
)
from backend.database.repositories.incident_repo import (
    IncidentEvidenceRepository,
    IncidentRepository,
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


def test_multiple_agent_runs_for_one_incident(db_session):
    inc_repo = IncidentRepository(db_session)
    ev_repo = IncidentEvidenceRepository(db_session)
    run_repo = AgentRunRepository(db_session)
    finding_repo = AgentFindingRepository(db_session)
    reasoning_repo = ReasoningResultRepository(db_session)

    incident = inc_repo.create(
        correlation_id="corr-999",
        title="Cascading farm crash",
        severity="CRITICAL",
        status="INVESTIGATING",
        event_type="NODE_UNHEALTHY",
        source_system="tractor",
    )

    evidence = ev_repo.create(
        incident_id=incident.id,
        evidence_type="NODE_METRICS",
        source="tractor",
        title="Thermal GPU log",
        structured_data={"temp": 94.0, "pcie_width": 1},
        captured_at=datetime.now(timezone.utc),
    )

    # 1. First Run: Supervisor Agent (iteration 1)
    sup_run_1 = run_repo.create(
        incident_id=incident.id,
        agent_name="IncidentSupervisor",
        agent_type="SUPERVISOR",
        status="COMPLETED",
        iteration=1,
        started_at=datetime.now(timezone.utc),
        output_summary="Delegated to HardwareDiagnosticAgent and RenderQAAgent",
        prompt_tokens=420,
        completion_tokens=150,
    )

    # 2. Second Run: Hardware Diagnostic Specialist Agent (iteration 1)
    hw_run = run_repo.create(
        incident_id=incident.id,
        agent_name="HardwareDiagnosticAgent",
        agent_type="SPECIALIST",
        status="COMPLETED",
        iteration=1,
        started_at=datetime.now(timezone.utc),
        prompt_tokens=600,
        completion_tokens=220,
    )

    # Findings produced by Hardware Diagnostic Agent, citing the evidence
    finding_1 = finding_repo.create(
        agent_run_id=hw_run.id,
        evidence_id=evidence.id,
        finding_type="THERMAL_THROTTLING",
        severity="CRITICAL",
        confidence=0.96,
        title="GPU temperature 94C exceeded safe operating limits",
        description="PCIe link width dropped from x16 to x1 due to thermal protection",
    )
    assert finding_1.evidence_id == evidence.id

    # 3. Third Run: Render QA Specialist Agent (iteration 1)
    render_run = run_repo.create(
        incident_id=incident.id,
        agent_name="RenderQAAgent",
        agent_type="SPECIALIST",
        status="COMPLETED",
        iteration=1,
        started_at=datetime.now(timezone.utc),
        prompt_tokens=550,
        completion_tokens=180,
    )

    # 4. Fourth Run: Supervisor Agent (iteration 2 - synthesis)
    sup_run_2 = run_repo.create(
        incident_id=incident.id,
        agent_name="IncidentSupervisor",
        agent_type="SUPERVISOR",
        status="COMPLETED",
        iteration=2,  # Second iteration!
        started_at=datetime.now(timezone.utc),
        prompt_tokens=850,
        completion_tokens=310,
    )

    # Verify that the incident contains ALL 4 agent runs
    all_runs = run_repo.list_by_incident(incident.id)
    assert len(all_runs) == 4
    agent_names = [r.agent_name for r in all_runs]
    assert agent_names == [
        "IncidentSupervisor",
        "HardwareDiagnosticAgent",
        "RenderQAAgent",
        "IncidentSupervisor",
    ]

    # Check iteration tracking
    assert run_repo.get_latest_iteration(incident.id, "IncidentSupervisor") == 2

    # Synthesized reasoning result linking run to root cause
    reasoning = reasoning_repo.create(
        incident_id=incident.id,
        agent_run_id=sup_run_2.id,
        root_cause="Compute blade thermal shutdown caused GPU bus de-negotiation and job crash",
        confidence=0.95,
        summary="Confirmed hardware fault on blade. Render jobs must be rescheduled onto healthy nodes.",
        hypotheses_evaluated=[
            {"hypothesis": "Software shader leak", "confidence": 0.12},
            {"hypothesis": "Hardware thermal throttling", "confidence": 0.96},
        ],
        evidence_refs=[evidence.id],
    )
    assert reasoning.id is not None
    assert reasoning.agent_run_id == sup_run_2.id
    assert reasoning.confidence == 0.95
