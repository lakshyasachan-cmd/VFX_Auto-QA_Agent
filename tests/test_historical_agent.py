"""
Unit and integration tests for the Historical Evidence Specialist Agent.
Tests verify:
1. Scenario 1: GPU Out-Of-Memory Benchmark (17 similar incidents, 14 resolved by RETRY_ON_80GB_GPU, confidence ~0.89)
2. Scenario 2: Strategy Success Rate Calculation (14 successes / 14 attempts for 80GB, 0/2 for same node)
3. Scenario 3: Thermal Overheating Precedents (quarantine vs daemon restart)
4. Scenario 4: Disk Space Exhaustion Precedents (scratch cache purge)
5. Scenario 5: Unmatched Incident Profile (confidence 0.0, zero invented evidence)
6. Scenario 6: Strict Distinction Between Current and Historical Evidence
7. Scenario 7: Enforced Safety Caveat Warning (Never assume past solution is automatically safe)
8. Scenario 8: Similarity Ranking and Threshold Filtering
9. Scenario 9: Google ADK Supervisor Contract Integration (async investigate)
10. Scenario 10: Read-Only Diagnostic Invariance (agent does not execute actions)
"""

import pytest

from backend.agents.historical.agent import HistoricalEvidenceAgent
from backend.agents.historical.similarity import compute_incident_similarity
from backend.agents.historical.tools import (
    calculate_historical_success_rate,
    get_previous_resolution,
    search_similar_incidents,
)


@pytest.fixture
def hist_agent():
    return HistoricalEvidenceAgent()


# ── Scenario 1: GPU OOM Benchmark (17 Incidents, 14 Resolved by 80GB) ─────────

def test_scenario_1_gpu_oom_canonical_benchmark(hist_agent):
    """
    Validates canonical benchmark:
    Current: GPU_OUT_OF_MEMORY
    Historical: 17 similar incidents, 14 successfully resolved by RETRY_ON_80GB_GPU, confidence ~0.89.
    """
    current_incident = {
        "incident_id": "inc-current-oom-01",
        "event_type": "RENDER_JOB_FAILED",
        "source": "deadline",
        "error_signature": "GPU_OUT_OF_MEMORY: CUDA out of memory allocation failure",
        "error_details": {
            "error_code": "GPU_OUT_OF_MEMORY",
            "message": "CUDA out of memory allocating buffer on blade node-42",
            "exit_code": 137,
        },
        "entity": {"node_id": "node-42", "job_id": "job-1042"},
    }

    report = hist_agent.analyze_incident(current_incident)

    # 1. Matches 17 similar incidents
    assert len(report.similar_incidents) == 17

    # 2. Output schema structure
    report_dict = report.model_dump()
    assert "similar_incidents" in report_dict
    assert "historical_patterns" in report_dict
    assert "recommended_precedents" in report_dict
    assert "confidence" in report_dict

    # 3. Confidence is approximately 0.89
    assert report.confidence == pytest.approx(0.89, abs=0.03)

    # 4. 14 successfully resolved by RETRY_ON_80GB_GPU
    top_rec = next(p for p in report.recommended_precedents if p.strategy == "RETRY_ON_80GB_GPU")
    assert top_rec.success_count == 14
    assert top_rec.sample_size == 14
    assert top_rec.success_rate == 1.0

    # 5. Evidence includes 14 resolved by RETRY_ON_80GB_GPU
    first_finding = report.findings[0]
    assert any("17 similar incident" in ev for ev in first_finding.evidence)
    assert any("14 successfully resolved by: RETRY_ON_80GB_GPU" in ev for ev in first_finding.evidence)


# ── Scenario 2: Strategy Success Rate Calculation ─────────────────────────────

def test_scenario_2_calculate_historical_success_rate(hist_agent):
    """Verifies success rate calculation across specific strategy attempts."""
    oom_ids = [f"hist-oom-{i:02d}" for i in range(1, 18)]

    # RETRY_ON_80GB_GPU: 14 attempts, 14 successes
    stats_80gb = calculate_historical_success_rate("RETRY_ON_80GB_GPU", oom_ids, store=hist_agent.store)
    assert stats_80gb["sample_size"] == 14
    assert stats_80gb["success_count"] == 14
    assert stats_80gb["failure_count"] == 0
    assert stats_80gb["success_rate"] == 1.0

    # RETRY_ON_SAME_NODE: 2 attempts, 0 successes
    stats_same = calculate_historical_success_rate("RETRY_ON_SAME_NODE", oom_ids, store=hist_agent.store)
    assert stats_same["sample_size"] == 2
    assert stats_same["success_count"] == 0
    assert stats_same["failure_count"] == 2
    assert stats_same["success_rate"] == 0.0

    # TEXTURE_DOWNSCALE_2K: 1 attempt, 1 success
    stats_tex = calculate_historical_success_rate("TEXTURE_DOWNSCALE_2K", oom_ids, store=hist_agent.store)
    assert stats_tex["sample_size"] == 1
    assert stats_tex["success_count"] == 1
    assert stats_tex["success_rate"] == 1.0


# ── Scenario 3: Thermal Overheating Precedents ────────────────────────────────

def test_scenario_3_thermal_overheating_precedents(hist_agent):
    """Verifies retrieval of thermal overheating precedents."""
    current_incident = {
        "incident_id": "inc-thermal-99",
        "event_type": "NODE_UNHEALTHY",
        "source": "deadline",
        "error_signature": "THERMAL_THROTTLING: GPU junction temperature 94C exceeded limit",
        "error_details": {"message": "Thermal shutdown slow down active", "temperature_c": 94.0},
    }

    report = hist_agent.analyze_incident(current_incident)
    assert len(report.similar_incidents) == 5

    # Top precedent should be BLADE_QUARANTINE_AND_COOL
    top_p = report.recommended_precedents[0]
    assert top_p.strategy == "BLADE_QUARANTINE_AND_COOL"
    assert top_p.success_count == 4
    assert top_p.sample_size == 4


# ── Scenario 4: Scratch Disk Full Precedents ──────────────────────────────────

def test_scenario_4_scratch_disk_full_precedents(hist_agent):
    """Verifies retrieval of scratch disk full precedents."""
    current_incident = {
        "incident_id": "inc-disk-99",
        "event_type": "NODE_UNHEALTHY",
        "source": "deadline",
        "error_signature": "DISK_SPACE_EXHAUSTION: ENOSPC: No space left on device",
        "error_details": {"message": "Failed to write buffer to /scratch mount", "error_code": "ENOSPC"},
    }

    report = hist_agent.analyze_incident(current_incident)
    assert len(report.similar_incidents) == 6

    top_p = report.recommended_precedents[0]
    assert top_p.strategy == "SCRATCH_CACHE_PURGE"
    assert top_p.success_count == 6
    assert top_p.success_rate == 1.0


# ── Scenario 5: Unmatched Incident Profile (Zero Invented Evidence) ───────────

def test_scenario_5_unmatched_incident_no_hallucination(hist_agent):
    """Unrecognized incident signature returns confidence 0.0 and zero invented evidence."""
    current_incident = {
        "incident_id": "inc-unknown-999",
        "event_type": "CUSTOM_APPLICATION_CRASH",
        "source": "in-house-tool",
        "error_signature": "UNRECOGNIZED_GPU_KERNEL_FAULT_XYZ_12345",
        "error_details": {"message": "Unknown kernel trap occurred in experimental procedural plugin"},
    }

    report = hist_agent.analyze_incident(current_incident)
    assert report.confidence == 0.0
    assert len(report.similar_incidents) == 0
    assert len(report.recommended_precedents) == 0

    first_finding = report.findings[0]
    assert first_finding.finding_type == "NO_HISTORICAL_PRECEDENTS_FOUND"
    assert len(first_finding.evidence) == 0  # STRICT: Zero invented evidence
    assert len(first_finding.observed) == 0
    assert len(first_finding.unknown) >= 1


# ── Scenario 6: Distinction Between Current and Historical Evidence ───────────

def test_scenario_6_distinguish_current_vs_historical_evidence(hist_agent):
    """Verifies explicit segregation of current incident telemetry from historical statistics."""
    current_incident = {
        "incident_id": "inc-current-oom-02",
        "event_type": "RENDER_JOB_FAILED",
        "source": "deadline",
        "error_signature": "GPU_OUT_OF_MEMORY: CUDA out of memory allocation failure",
        "entity": {"node_id": "render-node-77", "job_id": "job-777"},
    }

    report = hist_agent.analyze_incident(current_incident)

    # Current evidence is explicitly isolated
    assert report.current_evidence_summary["incident_id"] == "inc-current-oom-02"
    assert report.current_evidence_summary["node_id"] == "render-node-77"
    assert report.current_evidence_summary["error_signature"] == "GPU_OUT_OF_MEMORY: CUDA out of memory allocation failure"

    # Historical evidence is explicitly statistical
    assert len(report.similar_incidents) > 0
    for inc in report.similar_incidents:
        assert inc.incident_id != "inc-current-oom-02"
        assert inc.incident_id.startswith("hist-")


# ── Scenario 7: Safety Caveat Enforcement ─────────────────────────────────────

def test_scenario_7_safety_caveat_enforcement(hist_agent):
    """Verifies safety caveat: Never assume that a previous solution is automatically safe."""
    current_incident = {
        "incident_id": "inc-current-oom-03",
        "event_type": "RENDER_JOB_FAILED",
        "source": "deadline",
        "error_signature": "GPU_OUT_OF_MEMORY",
    }

    report = hist_agent.analyze_incident(current_incident)

    # 1. Report level safety caveats
    assert any("never assume" in c.lower() for c in report.safety_caveats)
    assert any("correlation" in c.lower() for c in report.safety_caveats)

    # 2. Precedent recommendation level caveats
    for p in report.recommended_precedents:
        assert any("never assume that a previous solution is automatically safe" in c.lower() for c in p.caveats)


# ── Scenario 8: Similarity Ranking & Filtering ────────────────────────────────

def test_scenario_8_similarity_ranking_and_filtering(hist_agent):
    """Verifies that candidates are ranked by score and low-similarity incidents are filtered."""
    current_incident = {
        "incident_id": "inc-ranking-test",
        "event_type": "RENDER_JOB_FAILED",
        "source": "deadline",
        "error_signature": "GPU_OUT_OF_MEMORY: CUDA out of memory",
    }

    similar = search_similar_incidents(current_incident, limit=10, min_similarity=0.5, store=hist_agent.store)
    assert len(similar) <= 10

    # Verify descending ordering
    for i in range(len(similar) - 1):
        assert similar[i].similarity_score >= similar[i + 1].similarity_score
        assert similar[i].similarity_score >= 0.5


# ── Scenario 9: Google ADK Supervisor Contract Integration ───────────────────

@pytest.mark.asyncio
async def test_scenario_9_supervisor_integration_contract(hist_agent):
    """Verifies that HistoricalEvidenceAgent satisfies the Google ADK BaseSpecialistAgent contract."""
    event = {
        "event_id": "evt-hist-001",
        "source": "deadline",
        "event_type": "RENDER_JOB_FAILED",
        "error_signature": "GPU_OUT_OF_MEMORY: CUDA out of memory allocation failure",
    }

    specialist_report = await hist_agent.investigate("inc-hist-001", event)

    assert specialist_report.agent_name == "HistoricalEvidenceAgent"
    assert specialist_report.status == "SUCCESS"
    assert len(specialist_report.findings) >= 1
    assert len(specialist_report.evidence) >= 1
    assert len(specialist_report.hypotheses) >= 1

    first_finding = specialist_report.findings[0]
    assert first_finding.agent_name == "HistoricalEvidenceAgent"
    assert first_finding.category == "history"
    assert first_finding.confidence == pytest.approx(0.89, abs=0.03)
    assert "safety_caveats" in first_finding.details
    assert "recommended_precedents" in first_finding.details


# ── Scenario 10: Non-Execution of Remediation Actions ─────────────────────────

def test_scenario_10_agent_does_not_execute_actions(hist_agent):
    """Verifies the agent strictly provides historical intelligence and never triggers actions."""
    current_incident = {
        "incident_id": "inc-non-exec",
        "event_type": "RENDER_JOB_FAILED",
        "source": "deadline",
        "error_signature": "GPU_OUT_OF_MEMORY",
    }

    report = hist_agent.analyze_incident(current_incident)
    report_dict = report.model_dump()

    assert "execute" not in report_dict
    assert "action_plan" not in report_dict
    assert "remediation_execution" not in report_dict
    assert "mcp" not in report_dict
    assert "dispatch" not in report_dict
