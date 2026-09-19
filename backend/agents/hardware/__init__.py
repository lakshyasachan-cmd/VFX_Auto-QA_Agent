"""
Hardware Diagnostics Specialist Agent module for Google ADK.
"""

from backend.agents.hardware.agent import HardwareDiagnosticAgent
from backend.agents.hardware.mock_telemetry import (
    HardwareTelemetryStore,
    telemetry_store,
)
from backend.agents.hardware.schemas import (
    CPUMetrics,
    DiskMetrics,
    DriverStatus,
    EpistemicStatus,
    GPUMetrics,
    HardwareFinding,
    HardwareReport,
    NodeHealth,
    NodeStatus,
)
from backend.agents.hardware.tools import (
    get_cpu_metrics,
    get_disk_metrics,
    get_driver_status,
    get_gpu_metrics,
    get_memory_metrics,
    get_node_health,
)

__all__ = [
    "HardwareDiagnosticAgent",
    "HardwareTelemetryStore",
    "telemetry_store",
    "NodeHealth",
    "NodeStatus",
    "GPUMetrics",
    "CPUMetrics",
    "MemoryMetrics",
    "DiskMetrics",
    "DriverStatus",
    "HardwareFinding",
    "HardwareReport",
    "EpistemicStatus",
    "get_node_health",
    "get_gpu_metrics",
    "get_cpu_metrics",
    "get_memory_metrics",
    "get_disk_metrics",
    "get_driver_status",
]
