"""
Mock telemetry provider and data store for VFX render nodes.
Simulates real-world compute blades across multiple hardware conditions:
- Healthy render blade
- GPU Out-Of-Memory exhaustion (CUDA OOM / 99.6% VRAM)
- Thermal overheating & PCIe throttling (94°C / PCIe x1 / 14 ECC errors)
- Disk space exhaustion (/scratch 99.99% full / ENOSPC)
- Driver failure (nvidia-smi communication lost / Xid 61 / driver hung)
- Offline / unregistered nodes (strictly missing telemetry)
"""

from typing import Any, Optional
from backend.agents.hardware.schemas import (
    CPUMetrics,
    DiskMetrics,
    DriverStatus,
    GPUMetrics,
    MemoryMetrics,
    NodeHealth,
    NodeStatus,
)


class HardwareTelemetryStore:
    """In-memory telemetry store for render blades and compute nodes."""

    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self._seed_default_telemetry()

    def _seed_default_telemetry(self) -> None:
        """Populate realistic test fixtures for compute blades."""

        # 1. Healthy Node
        healthy_nodes = ["node-healthy", "render-node-healthy", "render-node-01", "render-blade-01"]
        for nid in healthy_nodes:
            self.nodes[nid] = {
                "health": NodeHealth(
                    node_id=nid,
                    hostname=f"{nid}.farm.vfx.internal",
                    status=NodeStatus.HEALTHY,
                    uptime_hours=720.5,
                    consecutive_failures=0,
                    last_reboot="2026-08-01T00:00:00Z",
                    active_job_id="job_comp_101",
                    is_online=True,
                ),
                "gpu": GPUMetrics(
                    node_id=nid,
                    gpu_index=0,
                    gpu_model="NVIDIA RTX A6000",
                    memory_used_mb=12288.0,
                    memory_total_mb=49152.0,
                    memory_utilization_pct=25.0,
                    gpu_utilization_pct=45.0,
                    temperature_c=58.0,
                    throttle_status=None,
                    ecc_errors_uncorrectable=0,
                    pcie_link_width=16,
                    power_draw_w=180.0,
                    power_limit_w=300.0,
                ),
                "cpu": CPUMetrics(
                    node_id=nid,
                    cpu_model="AMD EPYC 7763 64-Core Processor",
                    core_count=64,
                    cpu_utilization_pct=35.0,
                    load_averages=[22.4, 21.8, 19.5],
                    temperature_c=48.0,
                ),
                "memory": MemoryMetrics(
                    node_id=nid,
                    total_ram_gb=256.0,
                    used_ram_gb=64.0,
                    free_ram_gb=192.0,
                    ram_utilization_pct=25.0,
                    swap_total_gb=32.0,
                    swap_used_gb=0.0,
                ),
                "disk": DiskMetrics(
                    node_id=nid,
                    mount_point="/scratch",
                    total_space_gb=4000.0,
                    used_space_gb=1200.0,
                    free_space_gb=2800.0,
                    disk_utilization_pct=30.0,
                    read_iops=120.0,
                    write_iops=250.0,
                    io_errors=0,
                    error_messages=[],
                ),
                "driver": DriverStatus(
                    node_id=nid,
                    driver_name="nvidia",
                    driver_version="535.129.03",
                    cuda_version="12.2",
                    compatible_renderers=["arnold-7.2.4", "vray-6.0", "renderman-25.2", "karma-20.0", "redshift-3.5"],
                    is_driver_responsive=True,
                    xid_errors=[],
                    error_message=None,
                ),
            }

        # 2. GPU OOM Node
        oom_nodes = ["node-gpu-oom", "render-node-gpu-oom", "render-node-42", "render-blade-oom"]
        for nid in oom_nodes:
            self.nodes[nid] = {
                "health": NodeHealth(
                    node_id=nid,
                    hostname=f"{nid}.farm.vfx.internal",
                    status=NodeStatus.DEGRADED,
                    uptime_hours=144.2,
                    consecutive_failures=2,
                    last_reboot="2026-09-02T12:00:00Z",
                    active_job_id="job_oom_arnold",
                    is_online=True,
                ),
                "gpu": GPUMetrics(
                    node_id=nid,
                    gpu_index=0,
                    gpu_model="NVIDIA GeForce RTX 4090",
                    memory_used_mb=24480.0,
                    memory_total_mb=24576.0,
                    memory_utilization_pct=99.6,
                    gpu_utilization_pct=100.0,
                    temperature_c=76.0,
                    throttle_status=None,
                    ecc_errors_uncorrectable=0,
                    pcie_link_width=16,
                    power_draw_w=420.0,
                    power_limit_w=450.0,
                ),
                "cpu": CPUMetrics(
                    node_id=nid,
                    cpu_model="Intel Xeon Platinum 8380",
                    core_count=40,
                    cpu_utilization_pct=45.0,
                    load_averages=[18.0, 16.5, 14.2],
                    temperature_c=52.0,
                ),
                "memory": MemoryMetrics(
                    node_id=nid,
                    total_ram_gb=128.0,
                    used_ram_gb=72.0,
                    free_ram_gb=56.0,
                    ram_utilization_pct=56.25,
                    swap_total_gb=16.0,
                    swap_used_gb=1.2,
                ),
                "disk": DiskMetrics(
                    node_id=nid,
                    mount_point="/scratch",
                    total_space_gb=2000.0,
                    used_space_gb=800.0,
                    free_space_gb=1200.0,
                    disk_utilization_pct=40.0,
                    read_iops=85.0,
                    write_iops=140.0,
                    io_errors=0,
                    error_messages=[],
                ),
                "driver": DriverStatus(
                    node_id=nid,
                    driver_name="nvidia",
                    driver_version="550.54.14",
                    cuda_version="12.4",
                    compatible_renderers=["arnold-7.2.4", "vray-6.0", "redshift-3.5"],
                    is_driver_responsive=True,
                    xid_errors=[
                        {
                            "code": 13,
                            "timestamp": "2026-09-08T16:44:59Z",
                            "message": "Graphics SM Exception: Out of memory buffer allocation failed (4096MB requested)",
                        }
                    ],
                    error_message="CUDA out of memory allocation failure",
                ),
            }

        # 3. Overheating Node
        thermal_nodes = ["node-overheating", "render-node-thermal", "render-blade-thermal"]
        for nid in thermal_nodes:
            self.nodes[nid] = {
                "health": NodeHealth(
                    node_id=nid,
                    hostname=f"{nid}.farm.vfx.internal",
                    status=NodeStatus.UNHEALTHY,
                    uptime_hours=48.0,
                    consecutive_failures=4,
                    last_reboot="2026-09-06T08:00:00Z",
                    active_job_id="job_thermal_trip",
                    is_online=True,
                ),
                "gpu": GPUMetrics(
                    node_id=nid,
                    gpu_index=0,
                    gpu_model="NVIDIA RTX A6000",
                    memory_used_mb=18400.0,
                    memory_total_mb=49152.0,
                    memory_utilization_pct=37.4,
                    gpu_utilization_pct=100.0,
                    temperature_c=94.0,  # Exceeds max 91C
                    throttle_status="SW_THERMAL_SLOWDOWN",
                    ecc_errors_uncorrectable=14,
                    pcie_link_width=1,  # Degraded from x16 to x1
                    power_draw_w=140.0,  # Clamped due to throttling
                    power_limit_w=300.0,
                ),
                "cpu": CPUMetrics(
                    node_id=nid,
                    cpu_model="AMD EPYC 7763 64-Core Processor",
                    core_count=64,
                    cpu_utilization_pct=85.0,
                    load_averages=[58.0, 52.1, 48.0],
                    temperature_c=89.0,  # High thermal
                ),
                "memory": MemoryMetrics(
                    node_id=nid,
                    total_ram_gb=256.0,
                    used_ram_gb=120.0,
                    free_ram_gb=136.0,
                    ram_utilization_pct=46.9,
                    swap_total_gb=32.0,
                    swap_used_gb=4.0,
                ),
                "disk": DiskMetrics(
                    node_id=nid,
                    mount_point="/scratch",
                    total_space_gb=4000.0,
                    used_space_gb=1500.0,
                    free_space_gb=2500.0,
                    disk_utilization_pct=37.5,
                    read_iops=40.0,
                    write_iops=60.0,
                    io_errors=0,
                    error_messages=[],
                ),
                "driver": DriverStatus(
                    node_id=nid,
                    driver_name="nvidia",
                    driver_version="535.129.03",
                    cuda_version="12.2",
                    compatible_renderers=["arnold-7.2.4", "vray-6.0"],
                    is_driver_responsive=True,
                    xid_errors=[
                        {
                            "code": 79,
                            "timestamp": "2026-09-08T16:30:10Z",
                            "message": "GPU has fallen off the bus due to thermal trip threshold exceedance (junction temp 94C)",
                        }
                    ],
                    error_message="Thermal shutdown protection triggered; clock frequencies throttled",
                ),
            }

        # 4. Disk Full Node
        disk_nodes = ["node-disk-full", "render-node-diskfull", "render-blade-diskfull"]
        for nid in disk_nodes:
            self.nodes[nid] = {
                "health": NodeHealth(
                    node_id=nid,
                    hostname=f"{nid}.farm.vfx.internal",
                    status=NodeStatus.DEGRADED,
                    uptime_hours=320.0,
                    consecutive_failures=3,
                    last_reboot="2026-08-20T10:00:00Z",
                    active_job_id="job_disk_full",
                    is_online=True,
                ),
                "gpu": GPUMetrics(
                    node_id=nid,
                    gpu_index=0,
                    gpu_model="NVIDIA RTX A6000",
                    memory_used_mb=8192.0,
                    memory_total_mb=49152.0,
                    memory_utilization_pct=16.6,
                    gpu_utilization_pct=10.0,
                    temperature_c=50.0,
                    throttle_status=None,
                    ecc_errors_uncorrectable=0,
                    pcie_link_width=16,
                    power_draw_w=120.0,
                    power_limit_w=300.0,
                ),
                "cpu": CPUMetrics(
                    node_id=nid,
                    cpu_model="Intel Xeon Gold 6348",
                    core_count=28,
                    cpu_utilization_pct=20.0,
                    load_averages=[4.2, 5.1, 5.0],
                    temperature_c=45.0,
                ),
                "memory": MemoryMetrics(
                    node_id=nid,
                    total_ram_gb=128.0,
                    used_ram_gb=32.0,
                    free_ram_gb=96.0,
                    ram_utilization_pct=25.0,
                    swap_total_gb=16.0,
                    swap_used_gb=0.0,
                ),
                "disk": DiskMetrics(
                    node_id=nid,
                    mount_point="/scratch",
                    total_space_gb=2000.0,
                    used_space_gb=1999.8,
                    free_space_gb=0.2,  # 200MB free
                    disk_utilization_pct=99.99,
                    read_iops=10.0,
                    write_iops=0.0,
                    io_errors=12,
                    error_messages=[
                        "ENOSPC: No space left on device",
                        "Failed to flush frame tile buffer to /scratch/tiles/tmp_1042.exr",
                    ],
                ),
                "driver": DriverStatus(
                    node_id=nid,
                    driver_name="nvidia",
                    driver_version="535.129.03",
                    cuda_version="12.2",
                    compatible_renderers=["arnold-7.2.4", "vray-6.0", "renderman-25.2"],
                    is_driver_responsive=True,
                    xid_errors=[],
                    error_message=None,
                ),
            }

        # 5. Driver Crash / Failure Node
        driver_nodes = ["node-driver-failure", "render-node-driver", "render-blade-driver"]
        for nid in driver_nodes:
            self.nodes[nid] = {
                "health": NodeHealth(
                    node_id=nid,
                    hostname=f"{nid}.farm.vfx.internal",
                    status=NodeStatus.UNHEALTHY,
                    uptime_hours=12.0,
                    consecutive_failures=5,
                    last_reboot="2026-09-08T04:00:00Z",
                    active_job_id="job_driver_crash",
                    is_online=True,
                ),
                "gpu": None,  # nvidia-smi failed to query
                "cpu": CPUMetrics(
                    node_id=nid,
                    cpu_model="AMD EPYC 7763 64-Core Processor",
                    core_count=64,
                    cpu_utilization_pct=15.0,
                    load_averages=[1.5, 2.0, 2.2],
                    temperature_c=42.0,
                ),
                "memory": MemoryMetrics(
                    node_id=nid,
                    total_ram_gb=128.0,
                    used_ram_gb=20.0,
                    free_ram_gb=108.0,
                    ram_utilization_pct=15.6,
                    swap_total_gb=16.0,
                    swap_used_gb=0.0,
                ),
                "disk": DiskMetrics(
                    node_id=nid,
                    mount_point="/scratch",
                    total_space_gb=2000.0,
                    used_space_gb=500.0,
                    free_space_gb=1500.0,
                    disk_utilization_pct=25.0,
                    read_iops=20.0,
                    write_iops=30.0,
                    io_errors=0,
                    error_messages=[],
                ),
                "driver": DriverStatus(
                    node_id=nid,
                    driver_name="nvidia",
                    driver_version="535.104.05",
                    cuda_version="unknown",
                    compatible_renderers=[],
                    is_driver_responsive=False,
                    xid_errors=[
                        {
                            "code": 61,
                            "timestamp": "2026-09-08T16:15:02Z",
                            "message": "Internal micro-controller warning: driver crash / lost communication with GPU",
                        },
                        {
                            "code": 999,
                            "timestamp": "2026-09-08T16:15:03Z",
                            "message": "nvidia-smi: Unable to communicate with NVIDIA driver: device handle lost",
                        },
                    ],
                    error_message="NVIDIA kernel module crashed; device handle lost; reboot required",
                ),
            }

    def get_node_data(self, node_id: str) -> Optional[dict[str, Any]]:
        """Fetch all telemetry for a given node_id, or None if unregistered."""
        return self.nodes.get(node_id)

    def register_node(self, node_id: str, data: dict[str, Any]) -> None:
        """Register or override a node telemetry record for testing."""
        self.nodes[node_id] = data

    def reset_defaults(self) -> None:
        """Reset store to default fixtures."""
        self.nodes.clear()
        self._seed_default_telemetry()


# Global telemetry store instance
telemetry_store = HardwareTelemetryStore()
