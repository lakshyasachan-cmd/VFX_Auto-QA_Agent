"""
Pydantic schemas for the Render QA Specialist Agent.
Enforces strict distinction between:
- OBSERVED: Directly extracted from raw logs, headers, or verified file telemetry.
- INFERRED: Deduced/hypothesized with confidence score based on observations.
- UNKNOWN: Explicitly missing, unverified, or unavailable information.
"""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class EpistemicStatus(str, Enum):
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class EpistemicFact(BaseModel):
    """Fact or assertion with explicit epistemological attribution."""
    model_config = ConfigDict(extra="ignore")

    status: EpistemicStatus = Field(..., description="OBSERVED, INFERRED, or UNKNOWN")
    statement: str
    source: str = Field(..., description="Origin (e.g., stderr_log, frame_header, deduction, missing_record)")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class FrameInspectionDetail(BaseModel):
    """Result of inspecting an individual frame."""
    model_config = ConfigDict(extra="ignore")

    frame: int
    status: str = Field(..., description="COMPLETED, FAILED, MISSING, CORRUPTED")
    exit_code: Optional[int] = None
    render_time_seconds: Optional[float] = None
    file_size_bytes: Optional[int] = None
    vram_peak_mb: Optional[float] = None
    error_snippet: Optional[str] = None
    node_id: Optional[str] = None


class FrameComparisonResult(BaseModel):
    """Comparison result between two frames in a sequence."""
    model_config = ConfigDict(extra="ignore")

    frame_a: int
    frame_b: int
    resolution_match: bool
    channel_match: bool
    size_ratio: float
    time_ratio: float
    is_consistent: bool
    discrepancies: list[str] = Field(default_factory=list)


class FrameCorruptionReport(BaseModel):
    """Detailed result of checking for corrupted pixel buffers or truncated files."""
    model_config = ConfigDict(extra="ignore")

    frame: int
    is_corrupted: bool
    corruption_type: Optional[str] = None  # ZERO_BYTE, NAN_PIXELS, TRUNCATED_HEADER, BLACK_FRAME
    nan_pixel_percentage: float = 0.0
    file_size_bytes: int = 0
    header_valid: bool = True
    details: str = "Frame intact"


class RenderQAFinding(BaseModel):
    """
    Standard finding structure required by the specification:
    {
      "agent": "render_qa",
      "finding_type": "...",
      "description": "...",
      "evidence": [...],
      "confidence": 0.0
    }
    """
    model_config = ConfigDict(extra="ignore")

    agent: str = Field(default="render_qa", description="Always 'render_qa'")
    finding_type: str = Field(..., description="e.g. GPU_OUT_OF_MEMORY, MISSING_FRAMES, CORRUPTED_FRAME")
    description: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    # Epistemic segregation
    observed: list[str] = Field(default_factory=list, description="Directly observed facts")
    inferred: list[str] = Field(default_factory=list, description="Inferred deductions with reasoning")
    unknown: list[str] = Field(default_factory=list, description="Explicitly unknown or missing facts")


class RenderQAReport(BaseModel):
    """Comprehensive investigation report produced by the Render QA agent."""
    model_config = ConfigDict(extra="ignore")

    agent: str = "render_qa"
    job_id: str
    renderer_info: dict[str, Any] = Field(default_factory=dict)
    findings: list[RenderQAFinding] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    failed_frames: list[int] = Field(default_factory=list)
    missing_frames: list[int] = Field(default_factory=list)
    corrupted_frames: list[int] = Field(default_factory=list)
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str
