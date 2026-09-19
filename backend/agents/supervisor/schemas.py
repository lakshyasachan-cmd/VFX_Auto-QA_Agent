"""
Strict Pydantic schemas for the Google ADK Supervisor Agent.
Defines input requests, output results, specialist reports, findings, and conflict schemas.
"""

from enum import Enum
from typing import Any, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class IncidentClassification(str, Enum):
    RENDER_FAILURE = "RENDER_FAILURE"
    HARDWARE_FAULT = "HARDWARE_FAULT"
    ASSET_ANOMALY = "ASSET_ANOMALY"
    OUTPUT_CORRUPTION = "OUTPUT_CORRUPTION"
    LIFECYCLE_EVENT = "LIFECYCLE_EVENT"
    UNKNOWN = "UNKNOWN"


class SpecialistName(str, Enum):
    RENDER_QA = "RenderQAAgent"
    HARDWARE_DIAGNOSTIC = "HardwareDiagnosticAgent"
    ASSET_VALIDATION = "AssetValidationAgent"
    HISTORICAL_EVIDENCE = "HistoricalEvidenceAgent"


class InvestigationStatus(str, Enum):
    INVESTIGATION_COMPLETE = "INVESTIGATION_COMPLETE"
    PARTIAL_INVESTIGATION = "PARTIAL_INVESTIGATION"
    INVESTIGATION_FAILED = "INVESTIGATION_FAILED"


class EvidenceItemDTO(BaseModel):
    """Normalized evidence gathered or cited during an investigation."""
    model_config = ConfigDict(extra="ignore")

    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evidence_type: str = Field(..., description="RENDER_LOG, NODE_TELEMETRY, USD_STAGE, FRAME_QC")
    source: str = Field(..., description="Origin system or agent name")
    title: str
    content: Optional[str] = None
    structured_data: dict[str, Any] = Field(default_factory=dict)


class AgentFindingDTO(BaseModel):
    """Specific diagnostic assertion or anomaly emitted by an agent."""
    model_config = ConfigDict(extra="ignore")

    finding_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str
    finding_type: str
    category: str = Field(default="software", description="software, hardware, asset, history")
    severity: str = Field(default="MEDIUM", description="CRITICAL, HIGH, MEDIUM, LOW, INFO")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    title: str
    description: Optional[str] = None
    evidence_ids: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class ConflictItem(BaseModel):
    """Represents contradictory findings across specialist agents."""
    model_config = ConfigDict(extra="ignore")

    conflict_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conflicting_agents: list[str]
    reason: str
    hypothesis_a: dict[str, Any]
    hypothesis_b: dict[str, Any]
    severity: str = Field(default="MEDIUM", description="HIGH, MEDIUM, LOW")


class AgentExecutionTrace(BaseModel):
    """Telemetry and status for a single specialist agent run."""
    model_config = ConfigDict(extra="ignore")

    agent_name: str
    status: str = Field(description="SUCCESS, FAILED, TIMED_OUT, SKIPPED")
    duration_ms: float = 0.0
    error: Optional[str] = None
    tokens_used: int = 0


class SpecialistReport(BaseModel):
    """Internal contract returned by specialist sub-agents to the supervisor."""
    model_config = ConfigDict(extra="ignore")

    agent_name: str
    status: str = Field(default="SUCCESS", description="SUCCESS, FAILED, TIMED_OUT")
    findings: list[AgentFindingDTO] = Field(default_factory=list)
    evidence: list[EvidenceItemDTO] = Field(default_factory=list)
    hypotheses: list[dict[str, Any]] = Field(default_factory=list)
    error_message: Optional[str] = None


class InvestigationRequest(BaseModel):
    """Input payload to trigger an investigation."""
    model_config = ConfigDict(extra="ignore")

    incident_id: str
    event: dict[str, Any] = Field(..., description="Canonical or raw VFX event payload")
    required_specialists: Optional[list[str]] = Field(
        default=None,
        description="Explicit specialist list override (e.g. ['RenderQAAgent'])",
    )
    timeout_seconds: float = Field(default=5.0, description="Per-specialist timeout in seconds")


class InvestigationResult(BaseModel):
    """
    Final structured investigation output produced by the Supervisor Agent.
    Strictly diagnostic; contains no action execution directives.
    """
    model_config = ConfigDict(extra="ignore")

    incident_id: str
    incident_type: IncidentClassification
    selected_specialists: list[str]
    findings: list[AgentFindingDTO] = Field(default_factory=list)
    evidence: list[EvidenceItemDTO] = Field(default_factory=list)
    conflicts: list[ConflictItem] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: InvestigationStatus
    summary: str
    agent_traces: list[AgentExecutionTrace] = Field(default_factory=list)
    root_cause_hypothesis: Optional[str] = None
    missing_data_warnings: list[str] = Field(default_factory=list)
