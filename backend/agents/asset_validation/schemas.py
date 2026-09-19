"""
Pydantic schemas for the VFX Asset Validation Specialist Agent.
Models asset nodes, dependency trees, integrity checks, and structured diagnostic findings.
STRICT INVARIANT: Agent only inspects and reports; NEVER modifies assets.
"""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class EpistemicStatus(str, Enum):
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class AssetType(str, Enum):
    USD = "USD"
    ALEMBIC = "ALEMBIC"
    OPENVDB = "OPENVDB"
    EXR_TEXTURE = "EXR_TEXTURE"
    SHADER = "SHADER"
    OTHER = "OTHER"


class AssetStatus(str, Enum):
    VALID = "VALID"
    MISSING = "MISSING"
    CORRUPTED = "CORRUPTED"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    INCOMPATIBLE = "INCOMPATIBLE"
    CYCLIC_REFERENCE = "CYCLIC_REFERENCE"


class AssetNode(BaseModel):
    """Represents an asset within the production repository graph."""
    model_config = ConfigDict(extra="ignore")

    asset_id: str
    file_path: str
    asset_type: AssetType
    version: str = "v001"
    expected_version: Optional[str] = None
    file_size_bytes: int = 1024
    exists_on_disk: bool = True
    is_corrupted: bool = False
    corruption_reason: Optional[str] = None
    dependencies: list[str] = Field(default_factory=list, description="IDs of referenced child assets")
    metadata: dict[str, Any] = Field(default_factory=dict)


class FileIntegrityResult(BaseModel):
    """Integrity check for a physical or cached file."""
    model_config = ConfigDict(extra="ignore")

    file_path: str
    asset_id: Optional[str] = None
    exists: bool = True
    is_intact: bool = True
    file_size_bytes: int = 0
    header_valid: bool = True
    error_message: Optional[str] = None


class DependencyCheckResult(BaseModel):
    """Result of full dependency tree traversal."""
    model_config = ConfigDict(extra="ignore")

    root_asset_id: str
    total_dependencies: int = 0
    visited_asset_ids: list[str] = Field(default_factory=list)
    missing_dependencies: list[str] = Field(default_factory=list)
    corrupt_dependencies: list[str] = Field(default_factory=list)
    dependency_chain: list[str] = Field(default_factory=list)
    dependency_graph: dict[str, list[str]] = Field(default_factory=dict)
    cycles_detected: list[list[str]] = Field(default_factory=list)


class VersionMismatchResult(BaseModel):
    """Version comparison against pipeline tracking system."""
    model_config = ConfigDict(extra="ignore")

    asset_id: str
    referenced_version: str
    expected_version: str
    is_mismatched: bool = False
    is_incompatible: bool = False
    details: str = "Version matches expected publish"


class AssetValidationFinding(BaseModel):
    """
    Standard finding structure required by the specification:
    {
      "agent": "asset_validation",
      "finding_type": "...",
      "severity": "...",
      "confidence": 0.0,
      "evidence": [...],
      "asset_ids": [...],
      "dependency_chain": [...]
    }
    """
    model_config = ConfigDict(extra="ignore")

    agent: str = Field(default="asset_validation", description="Always 'asset_validation'")
    finding_type: str = Field(..., description="e.g. MISSING_DEPENDENCY, CORRUPTED_ASSET, VERSION_MISMATCH")
    severity: str = Field(default="HIGH", description="CRITICAL, HIGH, MEDIUM, LOW, INFO")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    asset_ids: list[str] = Field(default_factory=list)
    dependency_chain: list[str] = Field(default_factory=list)

    # Epistemic segregation
    observed: list[str] = Field(default_factory=list, description="Direct empirical observations from asset headers/graph")
    inferred: list[str] = Field(default_factory=list, description="Inferred impact on downstream stage or render")
    unknown: list[str] = Field(default_factory=list, description="Explicitly unknown or uncollected information")
    details: dict[str, Any] = Field(default_factory=dict)


class AssetValidationReport(BaseModel):
    """Comprehensive asset validation report."""
    model_config = ConfigDict(extra="ignore")

    agent: str = "asset_validation"
    root_asset_id: str
    is_valid: bool = True
    total_assets_inspected: int = 0
    missing_asset_ids: list[str] = Field(default_factory=list)
    corrupt_asset_ids: list[str] = Field(default_factory=list)
    version_mismatches: list[str] = Field(default_factory=list)
    dependency_chain: list[str] = Field(default_factory=list)
    findings: list[AssetValidationFinding] = Field(default_factory=list)
    overall_confidence: float = 0.0
    summary: str = ""
