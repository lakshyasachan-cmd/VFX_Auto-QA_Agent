"""
Pydantic schemas for the Hardware Diagnostics Specialist Agent.
Enforces strict distinction between:
- OBSERVED: Directly extracted from physical hardware telemetry and OS counters.
- INFERRED: Deduced/hypothesized with confidence score based on observations.
- UNKNOWN: Explicitly missing, unverified, or unavailable telemetry.
DOES NOT execute remediation actions.
"""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class EpistemicStatus(str, Enum):
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class NodeStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    OFFLINE = "OFFLINE"


class NodeHealth(BaseModel):
    """Overall node health telemetry."""
    model_config = ConfigDict(extra="ignore")

    node_id: str
    hostname: str
    status: NodeStatus
    uptime_hours: float
    consecutive_failures: int = 0
    last_reboot: str
    active_job_id: Optional[str] = None
    is_online: bool = True


class GPUMetrics(BaseModel):
    """Detailed GPU telemetry from nvidia-smi / NVML."""
    model_config = ConfigDict(extra="ignore")

    node_id: str
    gpu_index: int = 0
    gpu_model: str
    memory_used_mb: float
    memory_total_mb: float
    memory_utilization_pct: float
    gpu_utilization_pct: float
    temperature_c: float
    throttle_status: Optional[str] = None  # None, "SW_THERMAL_SLOWDOWN", "HW_THERMAL_SLOWDOWN", "POWER_CAP"
    ecc_errors_uncorrectable: int = 0
    pcie_link_width: int = 16  # e.g., 16, 8, 4, 1
    power_draw_w: float = 0.0
    power_limit_w: float = 0.0


class CPUMetrics(BaseModel):
    """Detailed CPU telemetry."""
    model_config = ConfigDict(extra="ignore")

    node_id: str
    cpu_model: str
    core_count: int
    cpu_utilization_pct: float
    load_averages: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    temperature_c: float


class MemoryMetrics(BaseModel):
    """System RAM and Swap telemetry."""
    model_config = ConfigDict(extra="ignore")

    node_id: str
    total_ram_gb: float
    used_ram_gb: float
    free_ram_gb: float
    ram_utilization_pct: float
    swap_total_gb: float = 0.0
    swap_used_gb: float = 0.0


class DiskMetrics(BaseModel):
    """Storage metrics for /scratch, /tmp, or local render cache."""
    model_config = ConfigDict(extra="ignore")

    node_id: str
    mount_point: str
    total_space_gb: float
    used_space_gb: float
    free_space_gb: float
    disk_utilization_pct: float
    read_iops: float = 0.0
    write_iops: float = 0.0
    io_errors: int = 0
    error_messages: list[str] = Field(default_factory=list)


class DriverStatus(BaseModel):
    """GPU driver and kernel module status."""
    model_config = ConfigDict(extra="ignore")

    node_id: str
    driver_name: str
    driver_version: str
    cuda_version: str
    compatible_renderers: list[str] = Field(default_factory=list)
    is_driver_responsive: bool = True
    xid_errors: list[dict[str, Any]] = Field(default_factory=list)
    error_message: Optional[str] = None


class HardwareFinding(BaseModel):
    """
    Standard finding structure required by the specification:
    {
      "agent": "hardware_diagnostic",
      "finding_type": "...",
      "severity": "...",
      "confidence": 0.0,
      "evidence": [...]
    }
    """
    model_config = ConfigDict(extra="ignore")

    agent: str = Field(default="hardware_diagnostic", description="Always 'hardware_diagnostic'")
    finding_type: str = Field(..., description="e.g. GPU_MEMORY_EXHAUSTION, THERMAL_THROTTLING, DISK_FULL")
    severity: str = Field(default="HIGH", description="CRITICAL, HIGH, MEDIUM, LOW, INFO")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)

    # Epistemic segregation
    observed: list[str] = Field(default_factory=list, description="Direct empirical telemetry observed")
    inferred: list[str] = Field(default_factory=list, description="Inferred deductions from hardware state")
    unknown: list[str] = Field(default_factory=list, description="Explicitly missing or uncollected telemetry")
    details: dict[str, Any] = Field(default_factory=dict)


class HardwareReport(BaseModel):
    """Diagnostic report produced by the Hardware Diagnostics Agent."""
    model_config = ConfigDict(extra="ignore")

    agent: str = "hardware_diagnostic"
    node_id: str
    telemetry_available: bool
    node_health: Optional[dict[str, Any]] = None
    gpu_metrics: Optional[dict[str, Any]] = None
    cpu_metrics: Optional[dict[str, Any]] = None
    memory_metrics: Optional[dict[str, Any]] = None
    disk_metrics: Optional[dict[str, Any]] = None
    driver_status: Optional[dict[str, Any]] = None
    consecutive_failures: int = 0
    findings: list[HardwareFinding] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    overall_confidence: float = 0.0
    summary: str = ""
