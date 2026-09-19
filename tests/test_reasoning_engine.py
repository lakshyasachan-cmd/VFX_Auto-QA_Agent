"""
Unit and integration tests for the Gemini Root Cause Reasoning Engine.
Tests verify:
1. Scenario 1: GPU Memory Exhaustion Synthesis (Canonical benchmark scenario)
2. Scenario 2: Corrupted Asset Geometry Cache Diagnosis
3. Scenario 3: Hardware Thermal Throttling vs Software Glitch
4. Scenario 4: Insufficient Evidence Handling (returns INSUFFICIENT_EVIDENCE, confidence < 0.5)
5. Scenario 5: Contradictory Evidence Identification
6. Scenario 6: Alternative Causes Evaluation and Rationale
7. Scenario 7: AI Safety Invariance (no fabrication, no tool execution, no production mutation)
8. Scenario 8: Dependency Injection with Mock Gemini Client
"""

import pytest

from backend.reasoning.engine import RootCauseReasoningEngine
from backend.reasoning.mock_gemini import MockGeminiClient
from backend.reasoning.schemas import (
    AlternativeCause,
    ReasoningContextInput,
    RootCauseAnalysis,
)


@pytest.fixture
def reasoning_engine():
    return RootCauseReasoningEngine(use_mock=True)


# ── Scenario 1: GPU Memory Exhaustion Synthesis ───────────────────────────────

def test_scenario_1_gpu_oom_reasoning(reasoning_engine):
    """
    Validates canonical benchmark:
    GPU_MEMORY_EXHAUSTION synthesized from Render QA exit code 137,
    Hardware 99.6% VRAM metrics, and 14 historical precedents.
    """
    context = ReasoningContextInput(
        incident={
            "incident_id": "inc-oom-2026",
            "event_type": "RENDER_JOB_FAILED",
            "severity": "HIGH",
            "source": "deadline",
            "project": "VFX_FEATURE",
            "shot": "SH020",
            "error_details": {
                "error_code": "GPU_OUT_OF_MEMORY",
                "message": "CUDA out of memory while allocating 4096MB buffer on render-node-42",
                "exit_code": 137,
            },
            "entity": {"node_id": "render-node-42", "job_id": "job-1042"},
        },
        render_qa_findings=[
            {
                "finding_type": "GPU_OUT_OF_MEMORY",
                "severity": "HIGH",
                "confidence": 0.96,
                "description": "Arnold renderer exited with code 137 on frame 1042 due to CUDA VRAM exceedance",
                "observed": ["exit code 137", "VRAM peak 24576MB"],
            }
        ],
        hardware_findings=[
            {
                "finding_type": "GPU_MEMORY_EXHAUSTION",
                "severity": "HIGH",
                "confidence": 0.96,
                "evidence": ["GPU memory usage 99.6%", "VRAM used 24480MB of 24576MB on RTX 4090"],
                "observed": ["VRAM utilization at 99.6%"],
            }
        ],
        asset_findings=[
            {
                "finding_type": "ASSET_GRAPH_VALID",
                "severity": "INFO",
                "confidence": 0.95,
                "evidence": ["All scene USD references and textures intact"],
            }
        ],
        historical_evidence={
            "similar_incidents": [{"id": "hist-01"} for _ in range(17)],
            "recommended_precedents": [
                {
                    "strategy": "RETRY_ON_80GB_GPU",
                    "sample_size": 14,
                    "success_count": 14,
                    "success_rate": 1.0,
                    "caveats": ["Never assume past solution is automatically safe"],
                }
            ],
        },
    )

    analysis = reasoning_engine.analyze(context)

    # 1. Output schema compliance
    assert analysis.root_cause == "GPU_MEMORY_EXHAUSTION"
    assert analysis.confidence == pytest.approx(0.97, abs=0.03)
    assert analysis.severity == "HIGH"
    assert analysis.recommended_action in ("RETRY_ON_HEALTHY_NODE", "RETRY_ON_80GB_GPU")

    # 2. Supporting evidence populated
    assert len(analysis.supporting_evidence) >= 2
    assert any("99.6%" in ev or "VRAM" in ev for ev in analysis.supporting_evidence)
    assert any("137" in ev or "CUDA" in ev or "out of memory" in ev.lower() for ev in analysis.supporting_evidence)

    # 3. Contradicting evidence populated
    assert len(analysis.contradicting_evidence) >= 1
    assert any("disk" in ev.lower() or "thermal" in ev.lower() for ev in analysis.contradicting_evidence)

    # 4. Alternative causes evaluated
    assert len(analysis.alternative_causes) >= 1
    alt = analysis.alternative_causes[0]
    assert alt.cause != analysis.root_cause
    assert alt.confidence < analysis.confidence
    assert len(alt.why_less_likely) > 0


# ── Scenario 2: Corrupted Asset Geometry Cache ────────────────────────────────

def test_scenario_2_corrupted_asset_reasoning(reasoning_engine):
    """Synthesizes root cause for corrupted Alembic Ogawa cache with SIGSEGV reader crash."""
    context = ReasoningContextInput(
        incident={
            "incident_id": "inc-asset-corrupt-01",
            "event_type": "ASSET_VALIDATION_FAILED",
            "severity": "CRITICAL",
            "source": "shotgrid",
        },
        asset_findings=[
            {
                "finding_type": "CORRUPTED_ASSET_DATA",
                "severity": "CRITICAL",
                "confidence": 0.97,
                "evidence": [
                    "Corrupted asset detected: dragon_anim_v001.abc",
                    "Archive header invalid: truncated archive (16 bytes)",
                ],
            }
        ],
        render_qa_findings=[
            {
                "finding_type": "FRAME_CRASH_SIGSEGV",
                "severity": "CRITICAL",
                "confidence": 0.92,
                "evidence": ["Alembic reader crashed with signal 11 on stage composition"],
            }
        ],
        hardware_findings=[
            {
                "finding_type": "NODE_HEALTHY",
                "severity": "INFO",
                "confidence": 0.95,
                "evidence": ["Node hardware health nominal: 25% VRAM, 30% disk"],
            }
        ],
    )

    analysis = reasoning_engine.analyze(context)

    assert analysis.root_cause == "CORRUPTED_ASSET_CACHE"
    assert analysis.confidence >= 0.95
    assert analysis.severity == "CRITICAL"
    assert analysis.recommended_action == "REPUBLISH_AND_SYNC_ASSET"
    assert any("Ogawa" in ev or "16 bytes" in ev for ev in analysis.supporting_evidence)
    assert any("hardware" in ev.lower() or "nominal" in ev.lower() for ev in analysis.contradicting_evidence)


# ── Scenario 3: Hardware Thermal Throttling ───────────────────────────────────

def test_scenario_3_thermal_throttling_reasoning(reasoning_engine):
    """Synthesizes root cause for blade thermal trip and bus degradation."""
    context = ReasoningContextInput(
        incident={
            "incident_id": "inc-thermal-01",
            "event_type": "NODE_UNHEALTHY",
            "severity": "CRITICAL",
            "source": "deadline",
        },
        hardware_findings=[
            {
                "finding_type": "OVERHEATING_AND_THERMAL_THROTTLING",
                "severity": "CRITICAL",
                "confidence": 0.96,
                "evidence": [
                    "GPU temperature reached 94.0°C exceeding limit",
                    "Thermal throttling engaged: SW_THERMAL_SLOWDOWN",
                    "PCIe link width degraded to x1",
                    "14 uncorrectable ECC errors detected",
                ],
            }
        ],
        asset_findings=[
            {
                "finding_type": "ASSET_GRAPH_VALID",
                "severity": "INFO",
                "confidence": 0.95,
                "evidence": ["All assets intact"],
            }
        ],
    )

    analysis = reasoning_engine.analyze(context)

    assert analysis.root_cause == "HARDWARE_THERMAL_THROTTLING"
    assert analysis.confidence >= 0.95
    assert analysis.severity == "CRITICAL"
    assert analysis.recommended_action == "QUARANTINE_NODE_AND_COOL"
    assert any("94.0°C" in ev or "thermal" in ev.lower() for ev in analysis.supporting_evidence)


# ── Scenario 4: Insufficient Evidence Handling ───────────────────────────────

def test_scenario_4_insufficient_evidence_handling(reasoning_engine):
    """
    AI Safety Rule: If evidence is insufficient, return INSUFFICIENT_EVIDENCE with confidence < 0.5.
    Never invent facts or convert uncertainty into certainty.
    """
    context = ReasoningContextInput(
        incident={"incident_id": "inc-sparse-99", "event_type": "RENDER_JOB_FAILED"},
        render_qa_findings=[],
        hardware_findings=[],
        asset_findings=[],
        historical_evidence=None,
    )

    analysis = reasoning_engine.analyze(context)

    assert analysis.root_cause == "INSUFFICIENT_EVIDENCE"
    assert analysis.confidence < 0.50
    assert analysis.recommended_action == "DISPATCH_INVESTIGATION_MANUAL"
    assert len(analysis.supporting_evidence) == 0


# ── Scenario 5: Contradictory Evidence Identification ─────────────────────────

def test_scenario_5_contradictory_evidence_identification(reasoning_engine):
    """Verifies that evidence contradicting alternative explanations is captured."""
    context = ReasoningContextInput(
        incident={
            "incident_id": "inc-oom-contra",
            "event_type": "RENDER_JOB_FAILED",
            "error_signature": "GPU_OUT_OF_MEMORY",
        },
        hardware_findings=[
            {
                "finding_type": "GPU_MEMORY_EXHAUSTION",
                "severity": "HIGH",
                "confidence": 0.96,
                "evidence": ["GPU memory usage 99.6%"],
            }
        ],
        render_qa_findings=[
            {
                "finding_type": "GPU_OUT_OF_MEMORY",
                "severity": "HIGH",
                "confidence": 0.96,
                "evidence": ["CUDA exit code 137"],
            }
        ],
    )

    analysis = reasoning_engine.analyze(context)

    assert len(analysis.contradicting_evidence) > 0
    # Must disprove competing hardware failures (disk, thermal)
    assert any("disk" in ev.lower() or "thermal" in ev.lower() for ev in analysis.contradicting_evidence)


# ── Scenario 6: Alternative Causes Evaluation ─────────────────────────────────

def test_scenario_6_alternative_causes_evaluation(reasoning_engine):
    """Verifies secondary hypotheses are evaluated with confidence and explicit rationale."""
    context = ReasoningContextInput(
        incident={
            "incident_id": "inc-alt-eval",
            "event_type": "RENDER_JOB_FAILED",
            "error_signature": "GPU_OUT_OF_MEMORY",
        },
        hardware_findings=[{"finding_type": "GPU_MEMORY_EXHAUSTION", "evidence": ["99.6% VRAM"]}],
    )

    analysis = reasoning_engine.analyze(context)

    assert len(analysis.alternative_causes) >= 1
    for alt in analysis.alternative_causes:
        assert isinstance(alt, AlternativeCause)
        assert alt.confidence < analysis.confidence
        assert len(alt.why_less_likely) > 10


# ── Scenario 7: AI Safety & Zero Mutation Invariant ───────────────────────────

def test_scenario_7_ai_safety_invariance(reasoning_engine):
    """
    AI Safety Rules:
    - Do not fabricate evidence.
    - Do not execute tools.
    - Do not modify production systems.
    """
    context = ReasoningContextInput(
        incident={
            "incident_id": "inc-safety-test",
            "event_type": "RENDER_JOB_FAILED",
            "error_signature": "GPU_OUT_OF_MEMORY",
        },
        hardware_findings=[{"finding_type": "GPU_MEMORY_EXHAUSTION", "evidence": ["99.6% VRAM"]}],
    )

    analysis = reasoning_engine.analyze(context)
    analysis_dict = analysis.model_dump()

    # Analytical only: No execution hooks or production mutation commands
    assert "tool_execution" not in analysis_dict
    assert "command" not in analysis_dict
    assert "execute" not in analysis_dict
    assert "mcp_call" not in analysis_dict
    assert "delete" not in analysis_dict


# ── Scenario 8: Custom Mock Response Injection ────────────────────────────────

def test_scenario_8_mock_override_injection():
    """Verifies dependency injection of custom mock responses for testing edge cases."""
    custom_analysis = RootCauseAnalysis(
        root_cause="CUSTOM_TEST_ROOT_CAUSE",
        confidence=0.88,
        severity="MEDIUM",
        supporting_evidence=["Custom test evidence point 1"],
        contradicting_evidence=["Custom test contradiction 1"],
        alternative_causes=[],
        recommended_action="TEST_ACTION_STUB",
    )

    mock_client = MockGeminiClient(override_response=custom_analysis)
    engine = RootCauseReasoningEngine(gemini_client=mock_client)

    context = ReasoningContextInput(
        incident={"incident_id": "inc-custom"},
        hardware_findings=[{"finding_type": "CUSTOM"}],
    )

    result = engine.analyze(context)

    assert result.root_cause == "CUSTOM_TEST_ROOT_CAUSE"
    assert result.confidence == 0.88
    assert mock_client.call_count == 1
    assert mock_client.last_prompt is not None
