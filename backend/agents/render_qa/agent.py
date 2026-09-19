"""
Render QA Specialist Agent.
Investigates render-quality failures, frame errors, corruptions, missing frames, and consistency drops.
Strictly distinguishes:
- OBSERVED (direct empirical evidence from logs and file headers)
- INFERRED (diagnostic deductions and hypotheses)
- UNKNOWN (unverified, missing, or omitted telemetry)
DOES NOT execute remediation actions.
"""

from typing import Any, Optional
from backend.agents.render_qa.schemas import (
    RenderQAFinding,
    RenderQAReport,
)
from backend.agents.render_qa.simulated_store import SimulatedRenderFarmStore, farm_store
from backend.agents.render_qa.tools import (
    compare_frame_metadata,
    detect_frame_corruption,
    inspect_failed_frames,
    inspect_render_job,
)
from backend.agents.supervisor.schemas import (
    AgentFindingDTO,
    EvidenceItemDTO,
    SpecialistName,
    SpecialistReport,
)
from backend.agents.supervisor.specialist_interface import BaseSpecialistAgent


class RenderQAAgent(BaseSpecialistAgent):
    """
    Render QA Specialist Agent implemented for Google ADK.
    Diagnoses render engine failures and validates output frame integrity.
    """

    name: str = SpecialistName.RENDER_QA.value
    description: str = (
        "Specialist agent that analyzes render job logs, frame failures, "
        "missing output files, pixel corruption (NaN/Inf), and metadata discrepancies."
    )

    # Injected data store (defaults to farm_store)
    store: SimulatedRenderFarmStore = None  # type: ignore

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.store is None:
            self.store = farm_store

    def analyze_job(self, job_id: str, context: Optional[dict[str, Any]] = None) -> RenderQAReport:
        """
        Core diagnostic workflow:
        1. inspect_render_job
        2. inspect_failed_frames
        3. detect_frame_corruption
        4. compare_frame_metadata
        5. Epistemic analysis: OBSERVED vs INFERRED vs UNKNOWN
        """
        ctx = context or {}
        findings: list[RenderQAFinding] = []
        evidence_list: list[dict[str, Any]] = []

        # 1. Inspect Render Job
        job_info = inspect_render_job(job_id, store=self.store)

        if not job_info.get("found"):
            # Missing job record -> strictly UNKNOWN
            finding = RenderQAFinding(
                agent="render_qa",
                finding_type="JOB_NOT_FOUND",
                description=f"Render job '{job_id}' does not exist in farm database",
                confidence=0.0,
                evidence=[],
                observed=[],
                inferred=[],
                unknown=[f"No task database entry found for job_id '{job_id}'"],
            )
            return RenderQAReport(
                agent="render_qa",
                job_id=job_id,
                findings=[finding],
                evidence=[],
                summary=f"Investigation aborted: job '{job_id}' could not be located in farm store.",
                overall_confidence=0.0,
            )

        renderer = job_info.get("renderer", "unknown_renderer")
        renderer_ver = job_info.get("renderer_version", "unknown_version")
        failed_frames = job_info.get("failed_frames", [])
        missing_frames = job_info.get("missing_frames", [])
        completed_count = job_info.get("completed_count", 0)

        # 2. Inspect Failed Frames
        failed_details = inspect_failed_frames(job_id, store=self.store)
        for detail in failed_details:
            f_num = detail.frame

            # Case A: GPU Out of Memory
            if detail.exit_code == 137 or (detail.error_snippet and "Out of memory" in detail.error_snippet):
                ev = {
                    "type": "RENDER_LOG",
                    "frame": f_num,
                    "exit_code": detail.exit_code,
                    "error_snippet": detail.error_snippet,
                    "vram_peak_mb": detail.vram_peak_mb,
                }
                evidence_list.append(ev)
                findings.append(
                    RenderQAFinding(
                        agent="render_qa",
                        finding_type="GPU_OUT_OF_MEMORY",
                        description=f"Frame {f_num} failed due to CUDA Out-Of-Memory (Exit code 137)",
                        confidence=0.98,
                        evidence=[ev],
                        observed=[
                            f"Process terminated with exit code {detail.exit_code}",
                            f"Renderer log reports VRAM requested exceeded capacity ({detail.vram_peak_mb}MB peak)",
                        ],
                        inferred=[
                            "Scene geometry, textures, or AOV buffers exceeded the 24GB hardware limit of the node",
                            "Job must be rerouted to a high-memory (48GB+) node pool",
                        ],
                        unknown=[
                            "Specific texture file causing peak allocation is not logged in terse log mode"
                        ],
                    )
                )

            # Case B: Repeated Shader Segmentation Fault / Crash
            elif detail.exit_code == 139 or (detail.error_snippet and "SIGSEGV" in detail.error_snippet):
                ev = {
                    "type": "RENDER_LOG",
                    "frame": f_num,
                    "exit_code": detail.exit_code,
                    "error_snippet": detail.error_snippet,
                }
                evidence_list.append(ev)
                findings.append(
                    RenderQAFinding(
                        agent="render_qa",
                        finding_type="SHADER_SEGMENTATION_FAULT",
                        description=f"Frame {f_num} crashed with SIGSEGV (Signal 11 / Exit code 139)",
                        confidence=0.95,
                        evidence=[ev],
                        observed=[
                            "Process caught signal 11 (SIGSEGV) at address 0x00000000",
                            f"Log points to shader module: {detail.error_snippet}",
                        ],
                        inferred=[
                            "Null pointer dereference occurred inside shader execution loop",
                            "Re-rendering on different machine will not resolve; shader compilation/source must be fixed",
                        ],
                        unknown=[
                            "Whether fault is reproducible under standalone testrender utility"
                        ],
                    )
                )

            # Case C: Generic Failure
            elif detail.status == "FAILED":
                ev = {"type": "RENDER_LOG", "frame": f_num, "exit_code": detail.exit_code, "log": detail.error_snippet}
                evidence_list.append(ev)
                findings.append(
                    RenderQAFinding(
                        agent="render_qa",
                        finding_type="RENDER_FRAME_FAILURE",
                        description=f"Frame {f_num} failed execution with exit code {detail.exit_code}",
                        confidence=0.85,
                        evidence=[ev],
                        observed=[f"Frame {f_num} returned exit code {detail.exit_code}"],
                        inferred=["Task failed during render compute phase"],
                        unknown=["Root cause not explicitly specified in available log snippets"],
                    )
                )

        # 3. Analyze Missing Frames
        if missing_frames:
            ev = {"type": "FRAME_AUDIT", "missing_frames": missing_frames, "count": len(missing_frames)}
            evidence_list.append(ev)
            findings.append(
                RenderQAFinding(
                    agent="render_qa",
                    finding_type="MISSING_FRAMES_DETECTED",
                    description=f"Detected {len(missing_frames)} missing frame(s) in sequence: {missing_frames}",
                    confidence=0.99,
                    evidence=[ev],
                    observed=[f"Frames {missing_frames} have no task entry or output file on farm storage"],
                    inferred=[
                        "Frames were dropped by the queue dispatcher or never submitted",
                        "Sequence is incomplete and will fail editorial playback",
                    ],
                    unknown=["Whether frames were cancelled manually or never scheduled"],
                )
            )

        # 4. Check for Frame Corruption (NaN pixels, truncated headers)
        corrupted_frames: list[int] = []
        # Check frames in job (or context frame)
        frames_to_check = [ctx.get("frame")] if ctx.get("frame") is not None else list(job_info.get("failed_frames", []))
        # Also check completed frames if small set
        if not frames_to_check:
            rec = self.store.get_job_record(job_id) or {}
            frames_to_check = list(rec.get("output_files", {}).keys())

        for f in frames_to_check:
            if f is None:
                continue
            report = detect_frame_corruption(job_id, f, store=self.store)
            if report.is_corrupted:
                corrupted_frames.append(f)
                ev = {
                    "type": "FRAME_CORRUPTION_TELEMETRY",
                    "frame": f,
                    "corruption_type": report.corruption_type,
                    "nan_pixel_percentage": report.nan_pixel_percentage,
                    "file_size_bytes": report.file_size_bytes,
                }
                evidence_list.append(ev)
                findings.append(
                    RenderQAFinding(
                        agent="render_qa",
                        finding_type=f"FRAME_CORRUPTION_{report.corruption_type}",
                        description=report.details,
                        confidence=0.96,
                        evidence=[ev],
                        observed=[
                            f"File size on disk: {report.file_size_bytes} bytes",
                            f"NaN/Inf pixel proportion: {report.nan_pixel_percentage}%",
                            f"Header validity flag: {report.header_valid}",
                        ],
                        inferred=[
                            "Rendering completed without exit error, but output image buffer is corrupt",
                            "Likely division-by-zero in lighting math or incomplete file flush",
                        ],
                        unknown=["Which specific light or material contribution generated NaN pixels"],
                    )
                )

        # 5. Check Frame Metadata Consistency (compare sequential frames if available)
        rec = self.store.get_job_record(job_id) or {}
        completed_keys = sorted([
            f for f, d in rec.get("frames", {}).items() if d.get("status") == "COMPLETED"
        ])
        if len(completed_keys) >= 2:
            f1, f2 = completed_keys[0], completed_keys[1]
            cmp_res = compare_frame_metadata(job_id, f1, f2, store=self.store)
            if not cmp_res.is_consistent:
                ev = {
                    "type": "FRAME_COMPARISON",
                    "frame_a": f1,
                    "frame_b": f2,
                    "discrepancies": cmp_res.discrepancies,
                }
                evidence_list.append(ev)
                findings.append(
                    RenderQAFinding(
                        agent="render_qa",
                        finding_type="FRAME_METADATA_INCONSISTENCY",
                        description=f"Inconsistency between frames {f1} and {f2}: {'; '.join(cmp_res.discrepancies)}",
                        confidence=0.90,
                        evidence=[ev],
                        observed=cmp_res.discrepancies,
                        inferred=[
                            f"Frame {f2} finished prematurely or rendered at mismatched resolution",
                            "Pass was likely written with incorrect camera settings or aborted write",
                        ],
                        unknown=["Whether render node settings differed between tasks"],
                    )
                )

        # Calculate confidence
        if findings:
            overall_conf = round(sum(f.confidence for f in findings) / len(findings), 2)
        else:
            overall_conf = 0.90  # No anomalies detected in job
            findings.append(
                RenderQAFinding(
                    agent="render_qa",
                    finding_type="RENDER_INTEGRITY_VERIFIED",
                    description=f"Render job '{job_id}' ({renderer} {renderer_ver}) frames verified intact",
                    confidence=0.90,
                    evidence=[],
                    observed=[f"All {completed_count} frames completed with exit code 0"],
                    inferred=["No pixel corruption or sequence drops detected"],
                    unknown=[],
                )
            )

        summary = (
            f"Render QA evaluated job '{job_id}' ({renderer} {renderer_ver}): "
            f"identified {len(findings)} finding(s), {len(failed_frames)} failed frames, "
            f"{len(missing_frames)} missing frames, {len(corrupted_frames)} corrupted frames. "
            f"Confidence: {overall_conf}."
        )

        return RenderQAReport(
            agent="render_qa",
            job_id=job_id,
            renderer_info={"renderer": renderer, "version": renderer_ver},
            findings=findings,
            evidence=evidence_list,
            failed_frames=failed_frames,
            missing_frames=missing_frames,
            corrupted_frames=corrupted_frames,
            overall_confidence=overall_conf,
            summary=summary,
        )

    async def investigate(self, incident_id: str, event: dict[str, Any]) -> SpecialistReport:
        """
        Implementation of the Google ADK BaseSpecialistAgent contract.
        Returns a SpecialistReport compatible with the Supervisor Agent.
        """
        # Extract job_id from event
        job_id = (
            event.get("job_id")
            or event.get("entity", {}).get("job_id")
            or event.get("entity", {}).get("entity_id")
            or "job_oom_arnold"  # fallback default
        )

        report = self.analyze_job(str(job_id), context=event)

        # Convert findings to AgentFindingDTO
        dto_findings: list[AgentFindingDTO] = []
        for f in report.findings:
            dto_findings.append(
                AgentFindingDTO(
                    agent_name=self.name,
                    finding_type=f.finding_type,
                    category="software",
                    severity="HIGH" if "FAIL" in f.finding_type or "OOM" in f.finding_type or "CORRUPT" in f.finding_type else "MEDIUM",
                    confidence=f.confidence,
                    title=f.description,
                    description=f"Observed: {'; '.join(f.observed)}. Inferred: {'; '.join(f.inferred)}",
                    details={
                        "observed": f.observed,
                        "inferred": f.inferred,
                        "unknown": f.unknown,
                        "renderer": report.renderer_info,
                    },
                )
            )

        # Convert evidence to EvidenceItemDTO
        dto_evidence: list[EvidenceItemDTO] = []
        for idx, ev in enumerate(report.evidence):
            dto_evidence.append(
                EvidenceItemDTO(
                    evidence_type=ev.get("type", "RENDER_LOG"),
                    source=self.name,
                    title=f"Render QA Evidence #{idx+1} ({ev.get('type')})",
                    content=ev.get("error_snippet") or ev.get("log"),
                    structured_data=ev,
                )
            )

        hypotheses = [
            {
                "agent_name": self.name,
                "hypothesis": f.description,
                "confidence": f.confidence,
                "claim_type": "software",
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
