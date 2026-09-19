"""
Unit & integration tests for the Render QA Specialist Agent.
Tests verify:
1. Scenario 1: GPU Out-Of-Memory Frame Failure (Arnold exit code 137)
2. Scenario 2: Missing Frames in Sequence (V-Ray dropped tasks)
3. Scenario 3: Corrupted Output Frame (RenderMan NaN/Inf pixels & truncated header)
4. Scenario 4: Frame Metadata & Duration Inconsistency (Severe size and resolution mismatch)
5. Scenario 5: Repeated Failure Pattern Across Frames (Mantra SIGSEGV in custom shader)
6. Epistemic segregation: Strict distinction between OBSERVED, INFERRED, UNKNOWN
7. Zero invented evidence on missing jobs
8. Verification that agent does not execute remediation actions
"""

import pytest

from backend.agents.render_qa.agent import RenderQAAgent
from backend.agents.render_qa.tools import (
    compare_frame_metadata,
    detect_frame_corruption,
    inspect_failed_frames,
    inspect_render_job,
)


@pytest.fixture
def qa_agent():
    return RenderQAAgent()


# ── Scenario 1: GPU Out-Of-Memory Frame Failure (Arnold) ─────────────────────

def test_scenario_1_gpu_oom_failure(qa_agent):
    """Scenario 1: Detects Arnold CUDA OOM (Exit code 137, 24GB limit reached)."""
    # 1. Tool execution
    job_info = inspect_render_job("job_oom_arnold", store=qa_agent.store)
    assert job_info["found"] is True
    assert job_info["renderer"] == "arnold"
    assert 1042 in job_info["failed_frames"]

    failed_details = inspect_failed_frames("job_oom_arnold", store=qa_agent.store)
    assert len(failed_details) == 1
    assert failed_details[0].frame == 1042
    assert failed_details[0].exit_code == 137
    assert failed_details[0].vram_peak_mb == 24576
    assert "CUDA error: Out of memory" in failed_details[0].error_snippet

    # 2. Full agent analysis
    report = qa_agent.analyze_job("job_oom_arnold")
    assert report.job_id == "job_oom_arnold"
    assert report.renderer_info["renderer"] == "arnold"
    assert 1042 in report.failed_frames

    oom_finding = next(f for f in report.findings if f.finding_type == "GPU_OUT_OF_MEMORY")
    assert oom_finding.confidence >= 0.95

    # 3. Epistemic distinctions
    assert any("exit code 137" in obs for obs in oom_finding.observed)
    assert any("exceeded" in inf.lower() for inf in oom_finding.inferred)
    assert len(oom_finding.unknown) > 0  # Acknowledges specific texture allocation unlogged


# ── Scenario 2: Missing Frames in Sequence (V-Ray) ───────────────────────────

def test_scenario_2_missing_frames(qa_agent):
    """Scenario 2: Detects missing frames 1012-1015 in an expected sequence."""
    job_info = inspect_render_job("job_missing_frames", store=qa_agent.store)
    assert job_info["found"] is True
    assert job_info["missing_count"] == 4
    assert job_info["missing_frames"] == [1012, 1013, 1014, 1015]

    report = qa_agent.analyze_job("job_missing_frames")
    missing_finding = next(f for f in report.findings if f.finding_type == "MISSING_FRAMES_DETECTED")
    assert missing_finding.confidence >= 0.95
    assert "1012, 1013, 1014, 1015" in missing_finding.description

    # Epistemic distinctions
    assert any("1012, 1013, 1014, 1015" in obs for obs in missing_finding.observed)
    assert any("incomplete" in inf.lower() for inf in missing_finding.inferred)
    assert any("cancelled" in unk.lower() for unk in missing_finding.unknown)


# ── Scenario 3: Corrupted Output Frame (RenderMan NaN Pixels & Truncated Header)

def test_scenario_3_corrupted_frame_pixels_and_header(qa_agent):
    """Scenario 3: Detects 18.4% NaN pixels in beauty pass and 12-byte truncated header."""
    # Check Frame 1024: NaN pixels
    corrupt_1024 = detect_frame_corruption("job_corrupt_nan_pixels", 1024, store=qa_agent.store)
    assert corrupt_1024.is_corrupted is True
    assert corrupt_1024.corruption_type == "NAN_PIXELS"
    assert corrupt_1024.nan_pixel_percentage == 18.4

    # Check Frame 1025: Truncated header (12 bytes)
    corrupt_1025 = detect_frame_corruption("job_corrupt_nan_pixels", 1025, store=qa_agent.store)
    assert corrupt_1025.is_corrupted is True
    assert corrupt_1025.corruption_type == "TRUNCATED_HEADER"
    assert corrupt_1025.file_size_bytes == 12

    # Agent full analysis
    report = qa_agent.analyze_job("job_corrupt_nan_pixels", context={"frame": 1024})
    nan_finding = next(f for f in report.findings if "NAN_PIXELS" in f.finding_type)
    assert nan_finding.confidence >= 0.90
    assert any("18.4%" in obs for obs in nan_finding.observed)
    assert any("division-by-zero" in inf.lower() for inf in nan_finding.inferred)


# ── Scenario 4: Frame Metadata & Duration Inconsistency ──────────────────────

def test_scenario_4_frame_metadata_inconsistency(qa_agent):
    """Scenario 4: Detects 0.002x size drop and 1080p vs 4K resolution mismatch."""
    cmp_res = compare_frame_metadata("job_frame_inconsistency", 1001, 1002, store=qa_agent.store)
    assert cmp_res.is_consistent is False
    assert cmp_res.resolution_match is False
    assert cmp_res.channel_match is False
    assert cmp_res.size_ratio < 0.01  # severe size drop
    assert any("Resolution mismatch" in d for d in cmp_res.discrepancies)

    report = qa_agent.analyze_job("job_frame_inconsistency")
    inconsistency_finding = next(f for f in report.findings if f.finding_type == "FRAME_METADATA_INCONSISTENCY")
    assert inconsistency_finding.confidence >= 0.85
    assert any("Resolution mismatch" in obs for obs in inconsistency_finding.observed)
    assert any("prematurely" in inf.lower() for inf in inconsistency_finding.inferred)


# ── Scenario 5: Repeated Failure Pattern Across Frames (Mantra SIGSEGV) ──────

def test_scenario_5_repeated_shader_segfault(qa_agent):
    """Scenario 5: Identifies repeated SIGSEGV in custom shader across consecutive frames."""
    report = qa_agent.analyze_job("job_repeated_shader_segfault")
    assert len(report.failed_frames) == 3

    segfault_findings = [f for f in report.findings if f.finding_type == "SHADER_SEGMENTATION_FAULT"]
    assert len(segfault_findings) == 3
    first = segfault_findings[0]
    assert first.confidence >= 0.90

    # Check observed and inferred facts
    assert any("signal 11" in obs for obs in first.observed)
    assert any("libwood_procedural.so" in obs for obs in first.observed)
    assert any("null pointer" in inf.lower() for inf in first.inferred)
    assert any("re-rendering on different machine will not resolve" in inf.lower() for inf in first.inferred)


# ── Scenario 6: Missing / Unknown Job (No Invented Evidence) ─────────────────

def test_missing_job_records_unknown_no_hallucination(qa_agent):
    """Agent must return confidence 0.0 and explicit UNKNOWN facts when job record does not exist."""
    report = qa_agent.analyze_job("non_existent_ghost_job_999")
    assert report.overall_confidence == 0.0
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.finding_type == "JOB_NOT_FOUND"
    assert len(finding.evidence) == 0  # Never invents evidence!
    assert len(finding.unknown) == 1
    assert "No task database entry" in finding.unknown[0]


# ── Scenario 7: Google ADK Supervisor Integration Contract ───────────────────

@pytest.mark.asyncio
async def test_supervisor_integration_contract(qa_agent):
    """Verifies that RenderQAAgent implements the Google ADK BaseSpecialistAgent investigate contract."""
    event = {
        "source": "deadline",
        "event_type": "RENDER_JOB_FAILED",
        "job_id": "job_oom_arnold",
        "frame": 1042,
    }
    specialist_report = await qa_agent.investigate("inc-test-qa", event)

    assert specialist_report.agent_name == "RenderQAAgent"
    assert specialist_report.status == "SUCCESS"
    assert len(specialist_report.findings) >= 1
    assert len(specialist_report.evidence) >= 1
    assert len(specialist_report.hypotheses) >= 1

    first_finding = specialist_report.findings[0]
    assert first_finding.agent_name == "RenderQAAgent"
    assert first_finding.confidence >= 0.90
    assert "observed" in first_finding.details
    assert "inferred" in first_finding.details
    assert "unknown" in first_finding.details


# ── Scenario 8: Non-Execution Verification ───────────────────────────────────

def test_agent_does_not_execute_remediation(qa_agent):
    """Verifies the agent strictly produces diagnostics and does not trigger actions."""
    report = qa_agent.analyze_job("job_oom_arnold")
    report_dict = report.model_dump()

    assert "remediation" not in report_dict
    assert "execute" not in report_dict
    assert "action" not in report_dict
    assert "mcp" not in report_dict
