"""
Deterministic mock Gemini provider for the Root Cause Reasoning Engine.
Simulates structured outputs from Gemini without connecting to real production systems or APIs.
"""

from typing import Optional
from backend.reasoning.schemas import (
    AlternativeCause,
    ReasoningContextInput,
    RootCauseAnalysis,
)


class MockGeminiClient:
    """Mock Gemini client simulating google.genai generation with strict structured output."""

    def __init__(self, override_response: Optional[RootCauseAnalysis] = None) -> None:
        self.override_response = override_response
        self.call_count: int = 0
        self.last_prompt: Optional[str] = None

    def generate_analysis(
        self,
        context: ReasoningContextInput,
        prompt: str,
    ) -> RootCauseAnalysis:
        """Simulate Gemini analysis generation with strict schema output."""
        self.call_count += 1
        self.last_prompt = prompt

        if self.override_response is not None:
            return self.override_response

        # Check for insufficient evidence first
        has_rqa = bool(context.render_qa_findings)
        has_hw = bool(context.hardware_findings)
        has_asset = bool(context.asset_findings)
        has_err = bool(context.incident.get("error_details") or context.incident.get("error_signature"))

        if not (has_rqa or has_hw or has_asset or has_err):
            return RootCauseAnalysis(
                root_cause="INSUFFICIENT_EVIDENCE",
                confidence=0.20,
                severity="LOW",
                supporting_evidence=[],
                contradicting_evidence=[],
                alternative_causes=[],
                recommended_action="DISPATCH_INVESTIGATION_MANUAL",
                remediation_category="GOVERNANCE",
                reasoning_summary="No specialist agent telemetry or error details supplied to support a definitive diagnosis.",
                incident_id=context.incident.get("incident_id") or context.incident.get("event_id"),
            )

        # 1. Corrupted Frame / NaN Pixel Profile
        frame_corrupt_signals = (
            "FRAME_CORRUPTION" in str(context.incident.get("event_type", "")).upper()
            or "NAN" in str(context.incident).upper()
            or any("NAN" in str(f).upper() or "CORRUPT" in str(f).upper() for f in context.render_qa_findings)
        )
        if frame_corrupt_signals:
            return RootCauseAnalysis(
                root_cause="CORRUPTED_FRAME_NAN_PIXELS",
                confidence=0.94,
                severity="HIGH",
                supporting_evidence=[
                    "Render QA validator detected 24.8% NaN pixels in beauty pass EXR output",
                    "AOV inspection indicates unnormalized lighting calculations in hair shader",
                ],
                contradicting_evidence=[
                    "Compute node hardware temperature and memory utilization remained nominal",
                ],
                alternative_causes=[
                    AlternativeCause(
                        cause="GPU_PRECISION_OVERFLOW",
                        confidence=0.25,
                        supporting_evidence=["Half-float buffer calculation overflowed"],
                        why_less_likely="Shader logs pinpoint division by zero in microfacet BRDF roughness term",
                    )
                ],
                recommended_action="UPDATE_SHOT_STATUS_AND_NOTIFY",
                remediation_category="LOOKDEV_SHADER",
                reasoning_summary="Post-render QC detected illegal NaN values in exported frame beauty buffer caused by shader zero-division.",
                incident_id=context.incident.get("incident_id") or context.incident.get("event_id"),
            )

        # 2. GPU Memory Exhaustion Profile
        oom_signals = any(
            "OOM" in str(f) or "MEMORY" in str(f) or "CUDA" in str(f)
            for f in context.hardware_findings + context.render_qa_findings
        ) or "out of memory" in str(context.incident).lower() or "137" in str(context.incident)

        if oom_signals:
            return RootCauseAnalysis(
                root_cause="GPU_MEMORY_EXHAUSTION",
                confidence=0.97,
                severity="HIGH",
                supporting_evidence=[
                    "Hardware diagnostics reported 99.6% VRAM utilization",
                    "Render QA log indicates CUDA out of memory exit code 137",
                    "Historical precedent indicates 14 similar incidents were resolved by RETRY_ON_80GB_GPU",
                ],
                contradicting_evidence=[
                    "Scratch disk utilization at 40% with zero I/O errors",
                    "GPU temperature nominal at 76°C with no thermal throttling flags active",
                ],
                alternative_causes=[
                    AlternativeCause(
                        cause="TEXTURE_CACHE_OVERCONSUMPTION",
                        confidence=0.45,
                        supporting_evidence=["Render job beauty pass attempted to load high-res textures"],
                        why_less_likely="Hardware blade ran out of physical memory before mipmaps could finish streaming",
                    ),
                    AlternativeCause(
                        cause="SHADER_INFINITE_LOOP",
                        confidence=0.15,
                        supporting_evidence=["Frame took longer than average before aborting"],
                        why_less_likely="Explicit CUDA out-of-memory exit code 137 confirms resource exhaustion rather than hang",
                    ),
                ],
                recommended_action="RETRY_ON_HEALTHY_NODE",
                remediation_category="COMPUTE_INFRASTRUCTURE",
                reasoning_summary=(
                    "Physical VRAM on compute node was completely exhausted during frame render. "
                    "Render QA exit code 137, Hardware NVML metrics, and 14 historical precedents confirm "
                    "memory capacity breach rather than node silicon failure."
                ),
                incident_id=context.incident.get("incident_id") or context.incident.get("event_id"),
            )

        # 2. Corrupted Asset Profile
        asset_signals = any(
            "CORRUPT" in str(f) or "BROKEN" in str(f) or "Ogawa" in str(f)
            for f in context.asset_findings
        ) or "asset" in str(context.incident.get("event_type", "")).lower()

        if asset_signals:
            return RootCauseAnalysis(
                root_cause="CORRUPTED_ASSET_CACHE",
                confidence=0.96,
                severity="CRITICAL",
                supporting_evidence=[
                    "Asset validation detected truncated 16-byte Ogawa header in creature point cache",
                    "Render QA observed abort upon reading invalid file header",
                ],
                contradicting_evidence=[
                    "Node compute hardware reported nominal memory and disk health",
                ],
                alternative_causes=[
                    AlternativeCause(
                        cause="HARDWARE_GPU_BUS_ERROR",
                        confidence=0.10,
                        supporting_evidence=["Process terminated abruptly"],
                        why_less_likely="Blade telemetry reports 0 ECC errors and PCIe link width x16",
                    )
                ],
                recommended_action="REPUBLISH_AND_SYNC_ASSET",
                remediation_category="ASSET_STORAGE",
                reasoning_summary="Truncated geometry cache file caused downstream render delegate to crash upon stage composition.",
                incident_id=context.incident.get("incident_id") or context.incident.get("event_id"),
            )

        # 3. Thermal Throttling Profile
        thermal_signals = any(
            "THERMAL" in str(f) or "OVERHEAT" in str(f) or "94" in str(f)
            for f in context.hardware_findings
        )
        if thermal_signals:
            return RootCauseAnalysis(
                root_cause="HARDWARE_THERMAL_THROTTLING",
                confidence=0.95,
                severity="CRITICAL",
                supporting_evidence=[
                    "GPU junction temperature reached 94.0°C exceeding safety limit",
                    "NVML reported SW_THERMAL_SLOWDOWN with PCIe bandwidth degraded to x1",
                    "14 uncorrectable ECC errors detected on blade",
                ],
                contradicting_evidence=[
                    "Scene USD composition and geometry assets validated with 0 errors",
                ],
                alternative_causes=[
                    AlternativeCause(
                        cause="SOFTWARE_HANG",
                        confidence=0.20,
                        supporting_evidence=["Task slowed down dramatically"],
                        why_less_likely="Hardware clocks clamped by physical thermal protection rather than software loop",
                    )
                ],
                recommended_action="QUARANTINE_NODE_AND_COOL",
                remediation_category="COMPUTE_INFRASTRUCTURE",
                reasoning_summary="Compute blade experienced thermal trip threshold exceedance causing clock throttling and bus degradation.",
                incident_id=context.incident.get("incident_id") or context.incident.get("event_id"),
            )

        # Default fallback synthesis
        return RootCauseAnalysis(
            root_cause="UNKNOWN_PIPELINE_FAULT",
            confidence=0.55,
            severity="MEDIUM",
            supporting_evidence=["Diagnostic signals present but lack distinct root-cause pattern"],
            contradicting_evidence=[],
            alternative_causes=[],
            recommended_action="DISPATCH_INVESTIGATION_MANUAL",
            remediation_category="GOVERNANCE",
            reasoning_summary="Investigation yielded partial findings requiring manual TD review.",
            incident_id=context.incident.get("incident_id") or context.incident.get("event_id"),
        )
