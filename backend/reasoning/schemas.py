"""
Pydantic schemas for the Gemini Root Cause Reasoning Engine.
Defines strict structured output, alternative causes, and contextual inputs.
"""

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class AlternativeCause(BaseModel):
    """Represents an evaluated alternative hypothesis that was deemed less likely."""
    model_config = ConfigDict(extra="ignore")

    cause: str = Field(..., description="Hypothesized root cause")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score for this alternative")
    supporting_evidence: list[str] = Field(default_factory=list, description="Evidence lending plausibility")
    why_less_likely: str = Field(..., description="Rationale for why this cause is less probable than root_cause")


class RootCauseAnalysis(BaseModel):
    """
    Strict structured output conforming to user specification:
    {
      "root_cause": "GPU_MEMORY_EXHAUSTION",
      "confidence": 0.97,
      "severity": "HIGH",
      "supporting_evidence": [...],
      "contradicting_evidence": [...],
      "alternative_causes": [...],
      "recommended_action": "RETRY_ON_HEALTHY_NODE"
    }
    """
    model_config = ConfigDict(extra="ignore")

    root_cause: str = Field(..., description="Determined singular root cause, or 'INSUFFICIENT_EVIDENCE'")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Calibrated confidence score based strictly on evidence")
    severity: str = Field(default="HIGH", description="CRITICAL, HIGH, MEDIUM, LOW, INFO")
    supporting_evidence: list[str] = Field(default_factory=list, description="Direct facts and findings supporting root cause")
    contradicting_evidence: list[str] = Field(default_factory=list, description="Evidence weighing against alternative hypotheses")
    alternative_causes: list[AlternativeCause] = Field(default_factory=list, description="Evaluated secondary hypotheses")
    recommended_action: str = Field(..., description="Recommended remediation action or category")
    remediation_category: str = Field(default="COMPUTE_INFRASTRUCTURE", description="e.g. COMPUTE_INFRASTRUCTURE, ASSET_STORAGE, SOFTWARE, GOVERNANCE")
    reasoning_summary: str = Field(default="", description="High-level synthesis explaining the deduction")
    incident_id: Optional[str] = None


class ReasoningContextInput(BaseModel):
    """Input bundle combining the normalized incident and specialist agent reports."""
    model_config = ConfigDict(extra="ignore")

    incident: dict[str, Any] = Field(default_factory=dict, description="Normalized canonical VFX incident event")
    render_qa_findings: list[dict[str, Any]] = Field(default_factory=list, description="Findings from RenderQAAgent")
    hardware_findings: list[dict[str, Any]] = Field(default_factory=list, description="Findings from HardwareDiagnosticAgent")
    asset_findings: list[dict[str, Any]] = Field(default_factory=list, description="Findings from AssetValidationAgent")
    historical_evidence: Optional[dict[str, Any]] = Field(default=None, description="Report from HistoricalEvidenceAgent")
    additional_context: dict[str, Any] = Field(default_factory=dict)
