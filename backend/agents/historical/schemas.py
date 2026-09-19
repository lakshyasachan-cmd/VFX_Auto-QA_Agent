"""
Pydantic schemas for the Historical Evidence Specialist Agent.
Models historical incident similarity, prior resolutions, precedent success rates,
and strict safety boundaries.
"""

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class SimilarIncident(BaseModel):
    """A historical incident matched by the similarity mechanism."""
    model_config = ConfigDict(extra="ignore")

    incident_id: str
    title: str
    event_type: str
    error_signature: Optional[str] = None
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    status: str = "RESOLVED"
    resolved_at: Optional[str] = None
    resolution_summary: Optional[str] = None
    remediation_strategy: Optional[str] = None
    was_successful: bool = True
    context: dict[str, Any] = Field(default_factory=dict)


class HistoricalPattern(BaseModel):
    """Aggregate failure pattern identified across historical incidents."""
    model_config = ConfigDict(extra="ignore")

    pattern_name: str
    occurrence_count: int
    matching_error_signature: Optional[str] = None
    typical_root_cause: str
    prevalent_resolution: str


class PrecedentRecommendation(BaseModel):
    """Evaluation of a previous remediation strategy across historical matches."""
    model_config = ConfigDict(extra="ignore")

    strategy: str
    sample_size: int
    success_count: int
    failure_count: int
    success_rate: float = Field(..., ge=0.0, le=1.0)
    safety_assessment: str
    caveats: list[str] = Field(default_factory=list)


class HistoricalFinding(BaseModel):
    """
    Structured diagnostic finding emitted by the historical specialist.
    """
    model_config = ConfigDict(extra="ignore")

    agent: str = Field(default="historical_evidence", description="Always 'historical_evidence'")
    finding_type: str = Field(..., description="e.g. HISTORICAL_PRECEDENT_FOUND, HIGH_SUCCESS_PREVIOUS_STRATEGY")
    severity: str = Field(default="MEDIUM", description="CRITICAL, HIGH, MEDIUM, LOW, INFO")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    similar_incident_ids: list[str] = Field(default_factory=list)

    # Epistemic segregation
    observed: list[str] = Field(default_factory=list, description="Historical database records and empirical frequencies")
    inferred: list[str] = Field(default_factory=list, description="Inferred suitability of historical strategies")
    unknown: list[str] = Field(default_factory=list, description="Contextual differences not recorded in historical database")
    details: dict[str, Any] = Field(default_factory=dict)


class HistoricalEvidenceReport(BaseModel):
    """
    User specification compliant report:
    {
      "similar_incidents": [...],
      "historical_patterns": [...],
      "recommended_precedents": [...],
      "confidence": 0.89
    }
    """
    model_config = ConfigDict(extra="ignore")

    agent: str = "historical_evidence"
    current_incident_id: str
    similar_incidents: list[SimilarIncident] = Field(default_factory=list)
    historical_patterns: list[HistoricalPattern] = Field(default_factory=list)
    recommended_precedents: list[PrecedentRecommendation] = Field(default_factory=list)
    confidence: float = 0.0

    # Safety & Epistemic boundary
    safety_caveats: list[str] = Field(
        default_factory=lambda: [
            "Historical precedent indicates statistical correlation only, not guaranteed suitability.",
            "Never assume that a previous solution is automatically safe for the current incident.",
            "Current scene geometry, shader complexity, and farm node health must be independently verified.",
        ]
    )
    current_evidence_summary: dict[str, Any] = Field(default_factory=dict)
    findings: list[HistoricalFinding] = Field(default_factory=list)
    summary: str = ""
