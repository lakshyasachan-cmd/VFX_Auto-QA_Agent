"""
Mock Specialist Agents for testing the Google ADK Supervisor Agent.
Simulates Render QA, Hardware Diagnostic, Asset Validation, and Historical Evidence agents.
"""

import asyncio
from typing import Any, Optional
from backend.agents.supervisor.schemas import (
    AgentFindingDTO,
    EvidenceItemDTO,
    SpecialistName,
    SpecialistReport,
)
from backend.agents.supervisor.specialist_interface import BaseSpecialistAgent


class MockRenderQAAgent(BaseSpecialistAgent):
    name: str = SpecialistName.RENDER_QA.value
    description: str = "Specializes in render farm logs, shader crashes, frame aborts, and memory limits."
    custom_findings: Optional[list[AgentFindingDTO]] = None

    async def investigate(self, incident_id: str, event: dict[str, Any]) -> SpecialistReport:
        if self.delay_seconds > 0:
            await asyncio.sleep(self.delay_seconds)
        if self.should_fail:
            raise RuntimeError(self.failure_message)

        if self.custom_findings is not None:
            return SpecialistReport(
                agent_name=self.name,
                status="SUCCESS",
                findings=self.custom_findings,
            )

        # Default realistic analysis
        findings = [
            AgentFindingDTO(
                agent_name=self.name,
                finding_type="RENDER_ANOMALY",
                category="software",
                severity="HIGH",
                confidence=0.92,
                title="Arnold CUDA VRAM allocation failure on frame 1042",
                description="Process aborted due to GPU memory exceedance during beauty pass",
                details={"exit_code": 137, "renderer": "arnold-7.2.4"},
            )
        ]
        evidence = [
            EvidenceItemDTO(
                evidence_type="RENDER_LOG",
                source=self.name,
                title="Arnold Renderer Stderr Dump",
                content="[arnold] ERROR: Out of memory allocating 4096MB VRAM buffer on frame 1042",
                structured_data={"vram_allocated_mb": 24576},
            )
        ]
        return SpecialistReport(
            agent_name=self.name,
            status="SUCCESS",
            findings=findings,
            evidence=evidence,
            hypotheses=[
                {
                    "agent_name": self.name,
                    "hypothesis": "Scene textures exceeded 24GB VRAM",
                    "confidence": 0.92,
                }
            ],
        )


class MockHardwareDiagnosticAgent(BaseSpecialistAgent):
    name: str = SpecialistName.HARDWARE_DIAGNOSTIC.value
    description: str = "Specializes in compute blade diagnostics, thermal metrics, GPU bus status, and RAM."
    custom_findings: Optional[list[AgentFindingDTO]] = None

    async def investigate(self, incident_id: str, event: dict[str, Any]) -> SpecialistReport:
        if self.delay_seconds > 0:
            await asyncio.sleep(self.delay_seconds)
        if self.should_fail:
            raise RuntimeError(self.failure_message)

        if self.custom_findings is not None:
            return SpecialistReport(
                agent_name=self.name,
                status="SUCCESS",
                findings=self.custom_findings,
            )

        findings = [
            AgentFindingDTO(
                agent_name=self.name,
                finding_type="HARDWARE_STATUS",
                category="hardware",
                severity="CRITICAL",
                confidence=0.88,
                title="GPU PCIe link degraded to x1; thermal throttling observed",
                description="Blade reported 92C junction temperature with 14 uncorrectable ECC errors",
                details={"temp_c": 92.0, "pcie_width": 1},
            )
        ]
        evidence = [
            EvidenceItemDTO(
                evidence_type="NODE_TELEMETRY",
                source=self.name,
                title="Blade IPMI/NVIDIA-SMI Metrics",
                structured_data={"gpu_temp_c": 92.0, "pcie_link_width": 1, "ecc_errors": 14},
            )
        ]
        return SpecialistReport(
            agent_name=self.name,
            status="SUCCESS",
            findings=findings,
            evidence=evidence,
            hypotheses=[
                {
                    "agent_name": self.name,
                    "hypothesis": "Compute node hardware degradation caused job crash",
                    "confidence": 0.88,
                }
            ],
        )


class MockAssetValidationAgent(BaseSpecialistAgent):
    name: str = SpecialistName.ASSET_VALIDATION.value
    description: str = "Specializes in USD stage inspection, missing texture resolution, and Alembic validity."
    custom_findings: Optional[list[AgentFindingDTO]] = None

    async def investigate(self, incident_id: str, event: dict[str, Any]) -> SpecialistReport:
        if self.delay_seconds > 0:
            await asyncio.sleep(self.delay_seconds)
        if self.should_fail:
            raise RuntimeError(self.failure_message)

        if self.custom_findings is not None:
            return SpecialistReport(
                agent_name=self.name,
                status="SUCCESS",
                findings=self.custom_findings,
            )

        findings = [
            AgentFindingDTO(
                agent_name=self.name,
                finding_type="ASSET_MISSING",
                category="asset",
                severity="HIGH",
                confidence=0.95,
                title="Missing USD sublayer reference on network storage",
                description="File '/prod/assets/char/hero/tex/diffuse.1001.exr' does not exist",
                details={"missing_path": "/prod/assets/char/hero/tex/diffuse.1001.exr"},
            )
        ]
        evidence = [
            EvidenceItemDTO(
                evidence_type="USD_STAGE",
                source=self.name,
                title="USD Composition Graph Query",
                content="Failed to open layer: /prod/assets/char/hero/tex/diffuse.1001.exr",
                structured_data={"broken_links_count": 1},
            )
        ]
        return SpecialistReport(
            agent_name=self.name,
            status="SUCCESS",
            findings=findings,
            evidence=evidence,
        )


class MockHistoricalEvidenceAgent(BaseSpecialistAgent):
    name: str = SpecialistName.HISTORICAL_EVIDENCE.value
    description: str = "Specializes in pattern matching against resolved historical VFX pipeline incidents."
    custom_findings: Optional[list[AgentFindingDTO]] = None

    async def investigate(self, incident_id: str, event: dict[str, Any]) -> SpecialistReport:
        if self.delay_seconds > 0:
            await asyncio.sleep(self.delay_seconds)
        if self.should_fail:
            raise RuntimeError(self.failure_message)

        if self.custom_findings is not None:
            return SpecialistReport(
                agent_name=self.name,
                status="SUCCESS",
                findings=self.custom_findings,
            )

        findings = [
            AgentFindingDTO(
                agent_name=self.name,
                finding_type="HISTORICAL_MATCH",
                category="history",
                severity="INFO",
                confidence=0.85,
                title="Identical GPU OOM occurred 3 times in past 14 days on Project_A",
                description="Past incidents were resolved by rerouting to 48GB A6000 node pool",
                details={"past_incident_ids": ["inc-prev-001", "inc-prev-002"]},
            )
        ]
        evidence = [
            EvidenceItemDTO(
                evidence_type="HISTORICAL_RECORD",
                source=self.name,
                title="Incident Fingerprint Match",
                structured_data={"similar_incident_count": 3, "avg_resolution_time_min": 18.5},
            )
        ]
        return SpecialistReport(
            agent_name=self.name,
            status="SUCCESS",
            findings=findings,
            evidence=evidence,
        )
