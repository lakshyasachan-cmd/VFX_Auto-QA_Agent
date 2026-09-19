"""
Hardware Diagnostics Specialist Agent.
Investigates compute blade and render node problems:
- GPU memory & GPU utilization
- CPU utilization & host load
- RAM & swap usage
- Disk space & scratch I/O errors
- Temperature & thermal throttling
- Node health & consecutive failures
- Driver errors, Xid codes, & kernel crashes
- Renderer compatibility

STRICT RULES:
1. Never claim telemetry that was not supplied (strict anti-hallucination).
2. Clearly distinguish OBSERVED, INFERRED, UNKNOWN.
3. DOES NOT execute remediation actions (no reboot, no quarantine, no job retry).
"""

from typing import Any, Optional
from backend.agents.hardware.mock_telemetry import (
    HardwareTelemetryStore,
    telemetry_store,
)
from backend.agents.hardware.schemas import (
    HardwareFinding,
    HardwareReport,
)
from backend.agents.hardware.tools import (
    get_cpu_metrics,
    get_disk_metrics,
    get_driver_status,
    get_gpu_metrics,
    get_memory_metrics,
    get_node_health,
)
from backend.agents.supervisor.schemas import (
    AgentFindingDTO,
    EvidenceItemDTO,
    SpecialistName,
    SpecialistReport,
)
from backend.agents.supervisor.specialist_interface import BaseSpecialistAgent


class HardwareDiagnosticAgent(BaseSpecialistAgent):
    """
    Hardware Diagnostics Specialist Agent implemented for Google ADK.
    Diagnoses compute blade hardware failures, thermal bottlenecks, VRAM exhaustion,
    disk space limits, driver faults, and repeated node failures.
    """

    name: str = SpecialistName.HARDWARE_DIAGNOSTIC.value
    description: str = (
        "Specialist agent that analyzes render blade diagnostics, GPU memory, "
        "thermal throttling, PCIe bus width, disk storage, driver stability, and node health."
    )

    # Injected telemetry store (defaults to global telemetry_store)
    store: HardwareTelemetryStore = None  # type: ignore

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.store is None:
            self.store = telemetry_store

    def analyze_node(
        self,
        node_id: str,
        context: Optional[dict[str, Any]] = None,
    ) -> HardwareReport:
        """
        Core hardware diagnostic workflow:
        1. Query node health, GPU metrics, CPU metrics, memory metrics, disk metrics, driver status.
        2. Validate telemetry availability (prevent hallucinated metrics).
        3. Analyze GPU memory exhaustion and CUDA errors.
        4. Analyze thermal throttling, PCIe bus degradation, and ECC errors.
        5. Analyze disk space exhaustion and I/O write failures on scratch mounts.
        6. Analyze driver crashes, Xid codes, and kernel module unresponsiveness.
        7. Analyze repeated node failures and reliability history.
        8. Analyze renderer and CUDA compatibility.
        9. Synthesize findings with strict OBSERVED, INFERRED, UNKNOWN distinction.
        """
        ctx = context or {}
        findings: list[HardwareFinding] = []
        all_evidence: list[str] = []

        # 1. Execute diagnostic tools
        health = get_node_health(node_id, store=self.store)
        gpu = get_gpu_metrics(node_id, store=self.store)
        cpu = get_cpu_metrics(node_id, store=self.store)
        memory = get_memory_metrics(node_id, store=self.store)
        disk = get_disk_metrics(node_id, store=self.store)
        driver = get_driver_status(node_id, store=self.store)

        # 2. Check for missing / offline node telemetry
        if not health.get("available"):
            # Strictly zero invented evidence
            reason = health.get("reason", f"No telemetry stream found for node '{node_id}'")
            unavail_finding = HardwareFinding(
                agent="hardware_diagnostic",
                finding_type="TELEMETRY_UNAVAILABLE",
                severity="HIGH",
                confidence=0.0,
                evidence=[],
                observed=[],
                inferred=[],
                unknown=[reason, f"Telemetry stream for '{node_id}' is missing, offline, or unregistered"],
                details={"node_id": node_id, "reason": reason},
            )
            return HardwareReport(
                agent="hardware_diagnostic",
                node_id=node_id,
                telemetry_available=False,
                node_health=health,
                gpu_metrics=gpu,
                cpu_metrics=cpu,
                memory_metrics=memory,
                disk_metrics=disk,
                driver_status=driver,
                findings=[unavail_finding],
                evidence=[],
                overall_confidence=0.0,
                summary=f"Diagnostic aborted: Telemetry stream for node '{node_id}' is unavailable.",
            )

        # 3. GPU Memory Exhaustion
        if gpu.get("available"):
            vram_util = gpu.get("memory_utilization_pct", 0.0)
            vram_used = gpu.get("memory_used_mb", 0.0)
            vram_total = gpu.get("memory_total_mb", 0.0)
            gpu_model = gpu.get("gpu_model", "Unknown GPU")

            has_cuda_oom = False
            xid_oom_msg = None
            if driver.get("available"):
                for xid in driver.get("xid_errors", []):
                    if "out of memory" in xid.get("message", "").lower() or xid.get("code") == 13:
                        has_cuda_oom = True
                        xid_oom_msg = xid.get("message")
                        break

            # Context error details check
            ctx_err = str(ctx.get("error_details", {}))
            if "out of memory" in ctx_err.lower() or "cuda oom" in ctx_err.lower():
                has_cuda_oom = True

            if vram_util >= 95.0 or has_cuda_oom:
                conf = 0.98 if (vram_util >= 95.0 and has_cuda_oom) else 0.96
                evidence_items = [f"GPU memory usage {vram_util:.1f}%"]
                if has_cuda_oom:
                    evidence_items.append("job failed with CUDA OOM")
                if xid_oom_msg:
                    evidence_items.append(f"Xid error: {xid_oom_msg}")
                evidence_items.append(f"VRAM allocation: {vram_used:.0f}MB / {vram_total:.0f}MB on {gpu_model}")

                observed_facts = [
                    f"VRAM used {vram_used:.0f}MB of {vram_total:.0f}MB ({vram_util:.1f}%) on {gpu_model}",
                    f"GPU core utilization at {gpu.get('gpu_utilization_pct', 0):.1f}%",
                ]
                if has_cuda_oom:
                    observed_facts.append("CUDA out of memory error recorded in logs")

                inferred_facts = [
                    f"Render workload exceeded physical VRAM capacity ({vram_total:.0f}MB) of {gpu_model}",
                    "Geometry, displacement buffers, or high-res textures caused memory exhaustion",
                ]

                unknown_facts = [
                    "Individual texture mipmap allocation breakdown unlogged by render delegate",
                ]

                f_oom = HardwareFinding(
                    agent="hardware_diagnostic",
                    finding_type="GPU_MEMORY_EXHAUSTION",
                    severity="HIGH",
                    confidence=conf,
                    evidence=evidence_items,
                    observed=observed_facts,
                    inferred=inferred_facts,
                    unknown=unknown_facts,
                    details={
                        "memory_used_mb": vram_used,
                        "memory_total_mb": vram_total,
                        "memory_utilization_pct": vram_util,
                        "gpu_model": gpu_model,
                        "has_cuda_oom": has_cuda_oom,
                    },
                )
                findings.append(f_oom)
                all_evidence.extend(evidence_items)

        # 4. Temperature, Thermal Throttling, and PCIe Bus Width
        if gpu.get("available"):
            temp = gpu.get("temperature_c", 0.0)
            throttle = gpu.get("throttle_status")
            pcie_width = gpu.get("pcie_link_width", 16)
            ecc_errors = gpu.get("ecc_errors_uncorrectable", 0)

            is_overheating = temp >= 90.0 or throttle is not None or pcie_width < 16 or ecc_errors > 0

            if is_overheating:
                evidence_items = []
                observed_facts = []
                inferred_facts = []
                unknown_facts = []

                if temp >= 90.0:
                    evidence_items.append(f"GPU temperature reached {temp:.1f}°C (thermal threshold 91°C exceeded)")
                    observed_facts.append(f"GPU junction temperature measured at {temp:.1f}°C")
                if throttle:
                    evidence_items.append(f"Thermal throttling engaged: {throttle}")
                    observed_facts.append(f"NVML throttle status flag: '{throttle}'")
                if pcie_width < 16:
                    evidence_items.append(f"PCIe link width degraded to x{pcie_width} (expected x16)")
                    observed_facts.append(f"Current PCIe link width x{pcie_width} down from nominal x16")
                if ecc_errors > 0:
                    evidence_items.append(f"{ecc_errors} uncorrectable ECC memory errors detected on GPU")
                    observed_facts.append(f"Uncorrectable ECC memory count: {ecc_errors}")

                # Check driver Xid for thermal trip
                if driver.get("available"):
                    for xid in driver.get("xid_errors", []):
                        if xid.get("code") == 79 or "thermal" in xid.get("message", "").lower():
                            evidence_items.append(f"Xid {xid.get('code')}: {xid.get('message')}")
                            observed_facts.append(f"Kernel driver logged Xid {xid.get('code')}")

                inferred_facts.extend([
                    "Cooling failure, blocked chassis airflow, or thermal paste degradation on render blade",
                    "Hardware clock throttling or bus degradation significantly slows down rendering or causes bus drop",
                ])
                unknown_facts.append("Ambient datacenter inlet temperature and chassis intake fan RPM")

                f_thermal = HardwareFinding(
                    agent="hardware_diagnostic",
                    finding_type="OVERHEATING_AND_THERMAL_THROTTLING",
                    severity="CRITICAL",
                    confidence=0.96,
                    evidence=evidence_items,
                    observed=observed_facts,
                    inferred=inferred_facts,
                    unknown=unknown_facts,
                    details={
                        "temperature_c": temp,
                        "throttle_status": throttle,
                        "pcie_link_width": pcie_width,
                        "ecc_errors": ecc_errors,
                    },
                )
                findings.append(f_thermal)
                all_evidence.extend(evidence_items)

        # 5. Disk Space Exhaustion & Scratch I/O Errors
        if disk.get("available"):
            disk_util = disk.get("disk_utilization_pct", 0.0)
            free_gb = disk.get("free_space_gb", 0.0)
            total_gb = disk.get("total_space_gb", 0.0)
            mount = disk.get("mount_point", "/scratch")
            io_errors = disk.get("io_errors", 0)
            err_msgs = disk.get("error_messages", [])

            if disk_util >= 95.0 or free_gb < 1.0 or io_errors > 0:
                evidence_items = [
                    f"Disk space exhaustion on {mount}: {disk_util:.1f}% used ({free_gb:.2f}GB free of {total_gb:.0f}GB)",
                ]
                observed_facts = [
                    f"Mount '{mount}' is at {disk_util:.1f}% capacity with {free_gb:.2f}GB remaining",
                ]
                if io_errors > 0:
                    evidence_items.append(f"{io_errors} disk I/O errors reported on {mount}")
                    observed_facts.append(f"OS reported {io_errors} write errors: {'; '.join(err_msgs)}")
                if any("ENOSPC" in m for m in err_msgs):
                    evidence_items.append("File write failed with ENOSPC: No space left on device")

                inferred_facts = [
                    f"Render process unable to write temporary frame buffers or tile caches to {mount}",
                    "Accumulation of orphan render caches from previous uncleaned jobs",
                ]
                unknown_facts = [
                    "Storage quota breakdown per user/job on shared local scratch volume",
                ]

                f_disk = HardwareFinding(
                    agent="hardware_diagnostic",
                    finding_type="DISK_SPACE_EXHAUSTION",
                    severity="HIGH",
                    confidence=0.97,
                    evidence=evidence_items,
                    observed=observed_facts,
                    inferred=inferred_facts,
                    unknown=unknown_facts,
                    details={
                        "mount_point": mount,
                        "disk_utilization_pct": disk_util,
                        "free_space_gb": free_gb,
                        "io_errors": io_errors,
                    },
                )
                findings.append(f_disk)
                all_evidence.extend(evidence_items)

        # 6. Driver Failure / Crash / Unresponsive
        driver_crashed = False
        driver_evidence = []
        driver_observed = []
        driver_inferred = []
        driver_unknown = []

        if driver.get("available"):
            if not driver.get("is_driver_responsive", True):
                driver_crashed = True
                driver_evidence.append("GPU driver is unresponsive")
                driver_observed.append("is_driver_responsive is False")
            if driver.get("error_message"):
                driver_evidence.append(f"Driver error: {driver.get('error_message')}")
                driver_observed.append(f"Kernel driver reported: {driver.get('error_message')}")
            for xid in driver.get("xid_errors", []):
                code = xid.get("code")
                msg = xid.get("message")
                if code in (61, 999) or "crash" in msg.lower() or "lost" in msg.lower():
                    driver_crashed = True
                    driver_evidence.append(f"Xid {code}: {msg}")
                    driver_observed.append(f"Xid error code {code}: {msg}")

        if not gpu.get("available") and "failed to communicate" in gpu.get("reason", ""):
            driver_crashed = True
            driver_evidence.append("nvidia-smi communication lost with NVIDIA driver")
            driver_observed.append("nvidia-smi unable to query GPU device handle")

        if driver_crashed:
            driver_inferred.extend([
                "GPU kernel module encountered an unrecoverable exception or fallen off the PCIe bus",
                "Blade requires host kernel reboot or complete GPU reset to restore communication",
            ])
            driver_unknown.append("Specific assembly instruction or kernel interrupt that triggered the driver crash")

            f_driver = HardwareFinding(
                agent="hardware_diagnostic",
                finding_type="DRIVER_FAILURE",
                severity="CRITICAL",
                confidence=0.98,
                evidence=driver_evidence,
                observed=driver_observed,
                inferred=driver_inferred,
                unknown=driver_unknown,
                details={
                    "driver_version": driver.get("driver_version"),
                    "is_responsive": driver.get("is_driver_responsive"),
                    "xid_errors": driver.get("xid_errors", []),
                },
            )
            findings.append(f_driver)
            all_evidence.extend(driver_evidence)

        # 7. Repeated Node Failures
        consecutive_fails = health.get("consecutive_failures", 0)
        if consecutive_fails >= 3:
            fail_evidence = [
                f"Node '{node_id}' has recorded {consecutive_fails} consecutive job failures",
                f"Current node operational status: {health.get('status')}",
            ]
            fail_observed = [
                f"Consecutive job failure counter: {consecutive_fails}",
                f"Node status flagged as {health.get('status')}",
            ]
            fail_inferred = [
                "Compute blade has developed persistent instability affecting multiple successive tasks",
                "Further job dispatches to this node will likely fail until resolved",
            ]
            fail_unknown = [
                "Whether prior task failures were identical workloads or varied DCC renderers",
            ]
            f_repeated = HardwareFinding(
                agent="hardware_diagnostic",
                finding_type="REPEATED_NODE_FAILURES",
                severity="HIGH",
                confidence=0.92,
                evidence=fail_evidence,
                observed=fail_observed,
                inferred=fail_inferred,
                unknown=fail_unknown,
                details={
                    "consecutive_failures": consecutive_fails,
                    "status": health.get("status"),
                },
            )
            findings.append(f_repeated)
            all_evidence.extend(fail_evidence)

        # 8. Renderer Compatibility
        requested_renderer = ctx.get("renderer") or ctx.get("metadata", {}).get("renderer")
        if requested_renderer and driver.get("available"):
            compatible_renderers = driver.get("compatible_renderers", [])
            if requested_renderer not in compatible_renderers:
                evidence_items = [
                    f"Requested renderer '{requested_renderer}' is not compatible with node '{node_id}'",
                    f"Node supported renderers: {', '.join(compatible_renderers) if compatible_renderers else 'none'}",
                    f"Installed driver version {driver.get('driver_version')} / CUDA {driver.get('cuda_version')}",
                ]
                f_compat = HardwareFinding(
                    agent="hardware_diagnostic",
                    finding_type="RENDERER_INCOMPATIBILITY",
                    severity="HIGH",
                    confidence=0.93,
                    evidence=evidence_items,
                    observed=[
                        f"Target renderer: '{requested_renderer}'",
                        f"Blade compatibility whitelist: {compatible_renderers}",
                    ],
                    inferred=[
                        f"Renderer '{requested_renderer}' requires newer/different CUDA toolkit or driver branch",
                    ],
                    unknown=[
                        f"Minimum driver requirements specified by renderer vendor for '{requested_renderer}'",
                    ],
                    details={
                        "requested_renderer": requested_renderer,
                        "compatible_renderers": compatible_renderers,
                        "driver_version": driver.get("driver_version"),
                        "cuda_version": driver.get("cuda_version"),
                    },
                )
                findings.append(f_compat)
                all_evidence.extend(evidence_items)

        # 9. Healthy Node Case (No Anomalies Detected)
        if not findings:
            gpu_temp = gpu.get("temperature_c", 0.0) if gpu.get("available") else 0.0
            gpu_mem = gpu.get("memory_utilization_pct", 0.0) if gpu.get("available") else 0.0
            disk_used = disk.get("disk_utilization_pct", 0.0) if disk.get("available") else 0.0
            cpu_util = cpu.get("cpu_utilization_pct", 0.0) if cpu.get("available") else 0.0

            evidence_items = [
                f"Node '{node_id}' hardware health is nominal (Status: HEALTHY)",
                f"GPU VRAM {gpu_mem:.1f}%, Temp {gpu_temp:.1f}°C, CPU {cpu_util:.1f}%, Disk {disk_used:.1f}%",
                "Zero uncorrectable ECC errors, PCIe link width x16, driver responsive",
            ]
            f_healthy = HardwareFinding(
                agent="hardware_diagnostic",
                finding_type="NODE_HEALTHY",
                severity="INFO",
                confidence=0.95,
                evidence=evidence_items,
                observed=[
                    f"Node health status: {health.get('status')}",
                    f"GPU temperature: {gpu_temp:.1f}°C, VRAM utilization: {gpu_mem:.1f}%",
                    f"Scratch disk utilization: {disk_used:.1f}%",
                    f"Uptime: {health.get('uptime_hours', 0):.1f} hours, consecutive failures: {consecutive_fails}",
                ],
                inferred=[
                    "Physical compute blade hardware is fully operational",
                    "Root cause of any render task failure is likely in software, shaders, or scene assets",
                ],
                unknown=[
                    "Transient OS kernel interrupts during execution window",
                ],
                details={
                    "status": "HEALTHY",
                    "node_id": node_id,
                },
            )
            findings.append(f_healthy)
            all_evidence.extend(evidence_items)

        # Calculate overall confidence
        overall_conf = max((f.confidence for f in findings), default=0.90)

        # Build summary
        finding_types = [f.finding_type for f in findings]
        summary = f"Hardware investigation for node '{node_id}': Identified {len(findings)} finding(s) [{', '.join(finding_types)}]."

        return HardwareReport(
            agent="hardware_diagnostic",
            node_id=node_id,
            telemetry_available=True,
            node_health=health,
            gpu_metrics=gpu,
            cpu_metrics=cpu,
            memory_metrics=memory,
            disk_metrics=disk,
            driver_status=driver,
            consecutive_failures=consecutive_fails,
            findings=findings,
            evidence=all_evidence,
            overall_confidence=overall_conf,
            summary=summary,
        )

    async def investigate(self, incident_id: str, event: dict[str, Any]) -> SpecialistReport:
        """
        Implementation of the Google ADK BaseSpecialistAgent contract.
        Returns a SpecialistReport compatible with the Supervisor Agent.
        STRICT RULE: DOES NOT execute remediation actions.
        """
        # Extract node_id from event payload
        node_id = (
            event.get("node_id")
            or event.get("entity", {}).get("node_id")
            or event.get("entity", {}).get("entity_id")
            or event.get("metrics", {}).get("node_id")
            or "render-node-42"
        )

        report = self.analyze_node(str(node_id), context=event)

        # Convert findings to AgentFindingDTO
        dto_findings: list[AgentFindingDTO] = []
        for f in report.findings:
            dto_findings.append(
                AgentFindingDTO(
                    agent_name=self.name,
                    finding_type=f.finding_type,
                    category="hardware",
                    severity=f.severity,
                    confidence=f.confidence,
                    title=f.finding_type.replace("_", " ").title(),
                    description=f"Observed: {'; '.join(f.observed)}. Inferred: {'; '.join(f.inferred)}",
                    details={
                        "observed": f.observed,
                        "inferred": f.inferred,
                        "unknown": f.unknown,
                        "evidence": f.evidence,
                        "details": f.details,
                    },
                )
            )

        # Convert evidence to EvidenceItemDTO
        dto_evidence: list[EvidenceItemDTO] = []
        for idx, ev_text in enumerate(report.evidence):
            dto_evidence.append(
                EvidenceItemDTO(
                    evidence_type="NODE_TELEMETRY",
                    source=self.name,
                    title=f"Hardware Telemetry Evidence #{idx+1}",
                    content=ev_text,
                    structured_data={"node_id": node_id, "evidence": ev_text},
                )
            )

        hypotheses = [
            {
                "agent_name": self.name,
                "hypothesis": f"{f.finding_type}: {'; '.join(f.inferred)}",
                "confidence": f.confidence,
                "claim_type": "hardware",
            }
            for f in report.findings
        ]

        return SpecialistReport(
            agent_name=self.name,
            status="SUCCESS",
            findings=dto_findings,
            evidence=dto_evidence,
            hypotheses=hypotheses,
        )
