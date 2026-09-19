"""
Hardware diagnostic tools for inspecting compute blades and render nodes.
Functions:
1. get_node_health(node_id)
2. get_gpu_metrics(node_id)
3. get_cpu_metrics(node_id)
4. get_memory_metrics(node_id)
5. get_disk_metrics(node_id)
6. get_driver_status(node_id)

STRICT RULE: Never invent telemetry if a metric or node is not present.
Always return `available: False` and an explicit reason when telemetry is missing.
DOES NOT execute remediation actions.
"""

from typing import Any, Optional
from backend.agents.hardware.mock_telemetry import (
    HardwareTelemetryStore,
    telemetry_store,
)
from backend.agents.hardware.schemas import (
    CPUMetrics,
    DiskMetrics,
    DriverStatus,
    GPUMetrics,
    NodeHealth,
)


def get_node_health(
    node_id: str,
    store: Optional[HardwareTelemetryStore] = None,
) -> dict[str, Any]:
    """
    Retrieve overall operational health, uptime, failure count, and online status.
    Returns available=False if node telemetry is not present.
    """
    s = store or telemetry_store
    node_data = s.get_node_data(node_id)
    if not node_data or "health" not in node_data or node_data["health"] is None:
        return {
            "available": False,
            "node_id": node_id,
            "reason": f"No telemetry stream found for node '{node_id}' in telemetry registry.",
        }

    health: NodeHealth = node_data["health"]
    dump = health.model_dump(mode="json")
    dump["available"] = True
    return dump


def get_gpu_metrics(
    node_id: str,
    store: Optional[HardwareTelemetryStore] = None,
) -> dict[str, Any]:
    """
    Query NVML / nvidia-smi GPU metrics: VRAM utilization, GPU load, temperature,
    thermal throttling, PCIe link width, and ECC error counts.
    Returns available=False if GPU is unqueryable or node not found.
    """
    s = store or telemetry_store
    node_data = s.get_node_data(node_id)
    if not node_data:
        return {
            "available": False,
            "node_id": node_id,
            "reason": f"No telemetry stream found for node '{node_id}' in telemetry registry.",
        }

    gpu: Optional[GPUMetrics] = node_data.get("gpu")
    if gpu is None:
        return {
            "available": False,
            "node_id": node_id,
            "reason": f"GPU telemetry unavailable for node '{node_id}': nvidia-smi failed to communicate with device driver.",
        }

    dump = gpu.model_dump(mode="json")
    dump["available"] = True
    return dump


def get_cpu_metrics(
    node_id: str,
    store: Optional[HardwareTelemetryStore] = None,
) -> dict[str, Any]:
    """
    Query host CPU utilization, 1/5/15m load averages, and core temperatures.
    Returns available=False if node telemetry is not present.
    """
    s = store or telemetry_store
    node_data = s.get_node_data(node_id)
    if not node_data or "cpu" not in node_data or node_data["cpu"] is None:
        return {
            "available": False,
            "node_id": node_id,
            "reason": f"No telemetry stream found for node '{node_id}' in telemetry registry.",
        }

    cpu: CPUMetrics = node_data["cpu"]
    dump = cpu.model_dump(mode="json")
    dump["available"] = True
    return dump


def get_memory_metrics(
    node_id: str,
    store: Optional[HardwareTelemetryStore] = None,
) -> dict[str, Any]:
    """
    Query physical RAM and swap capacity, allocation, and utilization percentages.
    Returns available=False if node telemetry is not present.
    """
    s = store or telemetry_store
    node_data = s.get_node_data(node_id)
    if not node_data or "memory" not in node_data or node_data["memory"] is None:
        return {
            "available": False,
            "node_id": node_id,
            "reason": f"No telemetry stream found for node '{node_id}' in telemetry registry.",
        }

    mem: Any = node_data["memory"]
    dump = mem.model_dump(mode="json")
    dump["available"] = True
    return dump


def get_disk_metrics(
    node_id: str,
    store: Optional[HardwareTelemetryStore] = None,
) -> dict[str, Any]:
    """
    Query storage capacity, used/free space, IOPS, and write error logs on scratch mounts.
    Returns available=False if node telemetry is not present.
    """
    s = store or telemetry_store
    node_data = s.get_node_data(node_id)
    if not node_data or "disk" not in node_data or node_data["disk"] is None:
        return {
            "available": False,
            "node_id": node_id,
            "reason": f"No telemetry stream found for node '{node_id}' in telemetry registry.",
        }

    disk: DiskMetrics = node_data["disk"]
    dump = disk.model_dump(mode="json")
    dump["available"] = True
    return dump


def get_driver_status(
    node_id: str,
    store: Optional[HardwareTelemetryStore] = None,
) -> dict[str, Any]:
    """
    Query GPU driver version, CUDA toolkit compatibility, Xid error codes, and kernel responsiveness.
    Returns available=False if node telemetry is not present.
    """
    s = store or telemetry_store
    node_data = s.get_node_data(node_id)
    if not node_data or "driver" not in node_data or node_data["driver"] is None:
        return {
            "available": False,
            "node_id": node_id,
            "reason": f"No telemetry stream found for node '{node_id}' in telemetry registry.",
        }

    drv: DriverStatus = node_data["driver"]
    dump = drv.model_dump(mode="json")
    dump["available"] = True
    return dump
