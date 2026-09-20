"""
Incident Management Service for VFX Mission Control.
Manages querying, serializing, persisting, and real-time streaming of incidents,
bridging PostgreSQL database records, ADK investigation findings, and the Next.js dashboard.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, AsyncGenerator, Optional
import uuid

from sqlalchemy import desc, select
from sqlalchemy.orm import joinedload

from backend.database.models.agent import AgentFinding, AgentRun, ReasoningResult
from backend.database.models.incident import Incident, IncidentEvidence
from backend.database.models.remediation import Action, ApprovalRequest, RemediationPlan
from backend.database.session import SessionLocal

logger = logging.getLogger("vfx.incidents.service")

# In-memory queue of SSE subscribers for real-time incident event pushes
_sse_subscribers: list[asyncio.Queue] = []


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class IncidentService:
    """Service layer managing incidents, cluster health, and real-time SSE streaming."""

    def __init__(self) -> None:
        self._ensure_initial_seeds()

    def _ensure_initial_seeds(self) -> None:
        """Seed initial production incidents if the database is currently empty."""
        try:
            with SessionLocal() as db:
                count = db.query(Incident).count()
                if count == 0:
                    logger.info("Database has 0 incidents. Seeding default VFX incidents for Mission Control.")
                    self._seed_default_incidents(db)
        except Exception as e:
            logger.warning("Error checking or seeding default incidents: %s", e)

    def _seed_default_incidents(self, db) -> None:
        """Populate initial realistic VFX incidents in PostgreSQL."""
        seeds = [
            {
                "id": "inc-4362f983-solaris-oom",
                "correlation_id": "4362f983-ffb8-4e78-b4be-48dda2b6f5a0",
                "title": "Arnold GPU Out-Of-Memory (Exit 137)",
                "description": "Render task failed on node-blade-07 with CUDA Out-Of-Memory while allocating 4096MB buffer during frame 1042 beauty render.",
                "severity": "CRITICAL",
                "status": "AWAITING_APPROVAL",
                "event_type": "RENDER_JOB_FAILED",
                "source_system": "deadline",
                "error_signature": "GPU_OUT_OF_MEMORY",
                "project": "SOLARIS_VFX",
                "sequence": "SQ030",
                "shot": "SH0340",
                "job_id": "job-arnold-1777",
                "node_id": "node-blade-07",
                "created_at": datetime.now(timezone.utc),
                "evidence": [
                    {
                        "evidence_type": "RENDER_LOG",
                        "source": "deadline",
                        "title": "Deadline Slave Stderr Log",
                        "raw_content": "00:02:00 24576MB ERROR | [gpu] CUDA error: Out of memory while allocating 4096MB buffer.\nProcess exit code: 137",
                        "structured_data": {"exit_code": 137, "vram_peak_mb": 24576, "error_type": "GPU_OUT_OF_MEMORY"},
                    },
                    {
                        "evidence_type": "NODE_TELEMETRY",
                        "source": "nvidia-smi",
                        "title": "Worker GPU Telemetry",
                        "raw_content": "GPU 0: NVIDIA RTX A6000 | VRAM Used: 24576 / 24576 MB (100%)",
                        "structured_data": {"vram_used_pct": 100.0, "gpu_temp_c": 74.0},
                    },
                ],
                "agent_runs": [
                    {
                        "agent_name": "RenderQAAgent",
                        "agent_type": "RENDER_QA",
                        "status": "COMPLETED",
                        "output_summary": "Identified exit code 137 caused by scene VRAM exhaustion on frame 1042.",
                        "findings": [
                            {
                                "finding_type": "GPU_MEMORY_EXHAUSTION",
                                "severity": "CRITICAL",
                                "confidence": 0.98,
                                "title": "Frame 1042 exceeded 24GB VRAM capacity",
                                "description": "Renderer log reports requested VRAM exceeded capacity (28672MB requested, 24576MB available).",
                                "structured_payload": {
                                    "observed": ["Process terminated with exit code 137", "Peak memory: 24576MB"],
                                    "inferred": ["Scene geometry and texture buffers exceeded the 24GB hardware limit of the blade"],
                                    "unknown": [],
                                },
                            }
                        ],
                    },
                    {
                        "agent_name": "HardwareDiagnosticAgent",
                        "agent_type": "HARDWARE",
                        "status": "COMPLETED",
                        "output_summary": "Node health verified: 0 hardware ECC errors, driver responsive.",
                        "findings": [
                            {
                                "finding_type": "HARDWARE_CAPACITY_LIMIT",
                                "severity": "HIGH",
                                "confidence": 0.95,
                                "title": "Node A6000 hardware ceiling reached",
                                "description": "Blade node-blade-07 operating normally but insufficient for 28GB+ render requirement.",
                                "structured_payload": {
                                    "observed": ["PCIe link width x16", "ECC uncorrectable errors: 0"],
                                    "inferred": ["Hardware healthy; job requires rerouting to high-memory (48GB+) node pool"],
                                    "unknown": [],
                                },
                            }
                        ],
                    },
                ],
                "reasoning": {
                    "root_cause": "GPU_VRAM_EXHAUSTION",
                    "confidence": 0.96,
                    "severity": "CRITICAL",
                    "summary": "Frame 1042 failed due to Arnold GPU VRAM exhaustion on node-blade-07. Rerouting to 48GB GPU pool required.",
                    "supporting_evidence": ["Exit code 137 in Deadline log", "28672MB peak allocation requested"],
                    "contradicting_evidence": [],
                    "alternative_causes": [{"cause": "CORRUPTED_TEXTURE_BURST", "probability": 0.04}],
                    "recommended_action": "RETRY_JOB_HIGH_MEM_POOL",
                },
                "remediation": {
                    "strategy": "Re-queue failed frame on 48GB GPU blade pool and adjust render priority.",
                    "risk_level": "MEDIUM",
                    "requires_approval": True,
                    "actions": [
                        {
                            "action": "RETRY_JOB",
                            "reason": "Re-queue frame 1042 on high-memory pool gpu_48gb",
                            "risk": "MEDIUM",
                            "confidence": 0.95,
                            "requires_human_approval": True,
                            "parameters": {"target_pool": "gpu_48gb", "priority_boost": 15, "frame_range": "1042"},
                        },
                        {
                            "action": "NOTIFY_TEAM",
                            "reason": "Alert lighting TD of VRAM spike",
                            "risk": "LOW",
                            "confidence": 0.99,
                            "requires_human_approval": False,
                            "parameters": {"channel": "#lighting-tds", "message": "Frame 1042 failed on 24GB blade; rerouted to 48GB pool."},
                        },
                    ],
                },
            },
            {
                "id": "inc-8912ba01-dune-missing-frames",
                "correlation_id": "8912ba01-4432-4112-9901-778899aabbcc",
                "title": "V-Ray Dropped Frames in Sequence",
                "description": "Render sequence has 4 missing output EXR files (frames 1012-1015) following queue dispatcher timeout.",
                "severity": "HIGH",
                "status": "INVESTIGATING",
                "event_type": "RENDER_JOB_FAILED",
                "source_system": "deadline",
                "error_signature": "MISSING_OUTPUT_FRAMES",
                "project": "DUNE_PART_3",
                "sequence": "SQ020",
                "shot": "SH0010",
                "job_id": "job-vray-9100",
                "node_id": "render-node-15",
                "created_at": datetime.now(timezone.utc),
                "evidence": [
                    {
                        "evidence_type": "FRAME_QC",
                        "source": "storage_audit",
                        "title": "Farm Output Directory Scan",
                        "raw_content": "Missing frames in sequence: [1012, 1013, 1014, 1015]",
                        "structured_data": {"missing_frames": [1012, 1013, 1014, 1015]},
                    }
                ],
                "agent_runs": [],
                "reasoning": {
                    "root_cause": "DISPATCHER_TASK_DROP",
                    "confidence": 0.91,
                    "severity": "HIGH",
                    "summary": "Frames 1012-1015 were dropped during batch submission to the farm queue.",
                    "supporting_evidence": ["Output files 1012-1015 absent on farm storage mount"],
                    "contradicting_evidence": [],
                    "alternative_causes": [],
                    "recommended_action": "RETRY_MISSING_FRAMES",
                },
                "remediation": {
                    "strategy": "Re-submit missing frames 1012-1015 to deadline queue.",
                    "risk_level": "LOW",
                    "requires_approval": False,
                    "actions": [
                        {
                            "action": "RETRY_JOB",
                            "reason": "Render dropped frames 1012-1015",
                            "risk": "LOW",
                            "confidence": 0.95,
                            "requires_human_approval": False,
                            "parameters": {"frame_range": "1012-1015"},
                        }
                    ],
                },
            },
        ]

        for s in seeds:
            inc = Incident(
                id=s["id"],
                correlation_id=s["correlation_id"],
                title=s["title"],
                description=s["description"],
                severity=s["severity"],
                status=s["status"],
                event_type=s["event_type"],
                source_system=s["source_system"],
                error_signature=s["error_signature"],
                metadata_json={
                    "project": s["project"],
                    "sequence": s["sequence"],
                    "shot": s["shot"],
                    "job_id": s["job_id"],
                    "node_id": s["node_id"],
                },
                created_at=s["created_at"],
            )
            db.add(inc)
            db.flush()

            for ev in s.get("evidence", []):
                db.add(
                    IncidentEvidence(
                        incident_id=inc.id,
                        evidence_type=ev["evidence_type"],
                        source=ev["source"],
                        title=ev["title"],
                        raw_content=ev.get("raw_content"),
                        structured_data=ev.get("structured_data", {}),
                        captured_at=datetime.now(timezone.utc),
                    )
                )

            for ar in s.get("agent_runs", []):
                run = AgentRun(
                    incident_id=inc.id,
                    agent_name=ar["agent_name"],
                    agent_type=ar["agent_type"],
                    status=ar["status"],
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                    output_summary=ar.get("output_summary"),
                )
                db.add(run)
                db.flush()

                for f in ar.get("findings", []):
                    db.add(
                        AgentFinding(
                            agent_run_id=run.id,
                            finding_type=f["finding_type"],
                            severity=f["severity"],
                            confidence=f["confidence"],
                            title=f["title"],
                            description=f.get("description"),
                            structured_payload=f.get("structured_payload", {}),
                        )
                    )

            if "reasoning" in s:
                r = s["reasoning"]
                rr = ReasoningResult(
                    incident_id=inc.id,
                    root_cause=r["root_cause"],
                    confidence=r["confidence"],
                    summary=r["summary"],
                    hypotheses_evaluated=r.get("alternative_causes", []),
                    evidence_refs=[],
                )
                db.add(rr)
                db.flush()

                if "remediation" in s:
                    rem = s["remediation"]
                    plan = RemediationPlan(
                        incident_id=inc.id,
                        reasoning_result_id=rr.id,
                        strategy=rem["strategy"],
                        risk_level=rem["risk_level"],
                        requires_approval=rem["requires_approval"],
                    )
                    db.add(plan)
                    db.flush()

                    for a in rem.get("actions", []):
                        act = Action(
                            plan_id=plan.id,
                            action_type=a["action"],
                            tool_name=a["action"].lower(),
                            parameters=a.get("parameters", {}),
                            status="PENDING",
                        )
                        db.add(act)

                        appr = ApprovalRequest(
                            plan_id=plan.id,
                            status="PENDING" if a["requires_human_approval"] else "AUTO_APPROVED",
                            requested_at=datetime.now(timezone.utc),
                            policy_evaluated={"action": a["action"], "risk": a["risk"], "confidence": a["confidence"]},
                        )
                        db.add(appr)

        db.commit()
        logger.info("Successfully seeded default VFX incidents in PostgreSQL.")

    def list_incidents(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Retrieve incidents list formatted for the Next.js IncidentGrid."""
        try:
            with SessionLocal() as db:
                query = (
                    select(Incident)
                    .options(
                        joinedload(Incident.evidence),
                        joinedload(Incident.agent_runs).joinedload(AgentRun.findings),
                        joinedload(Incident.reasoning_results),
                        joinedload(Incident.remediation_plans)
                        .joinedload(RemediationPlan.approval_requests),
                        joinedload(Incident.remediation_plans)
                        .joinedload(RemediationPlan.actions),
                    )
                    .order_by(desc(Incident.created_at))
                    .limit(limit)
                )
                if status:
                    query = query.filter(Incident.status == status.upper())
                if severity:
                    query = query.filter(Incident.severity == severity.upper())

                records = db.execute(query).unique().scalars().all()
                return [self._serialize_incident(inc) for inc in records]
        except Exception as e:
            logger.error("Error listing incidents from database: %s", e)
            return []

    def get_incident(self, incident_id: str) -> Optional[dict[str, Any]]:
        """Retrieve single incident by ID with full investigation graph."""
        try:
            with SessionLocal() as db:
                query = (
                    select(Incident)
                    .options(
                        joinedload(Incident.evidence),
                        joinedload(Incident.agent_runs).joinedload(AgentRun.findings),
                        joinedload(Incident.reasoning_results),
                        joinedload(Incident.remediation_plans)
                        .joinedload(RemediationPlan.approval_requests),
                        joinedload(Incident.remediation_plans)
                        .joinedload(RemediationPlan.actions),
                    )
                    .filter(Incident.id == incident_id)
                )
                inc = db.execute(query).unique().scalar_one_or_none()
                if inc:
                    return self._serialize_incident(inc)
        except Exception as e:
            logger.error("Error fetching incident '%s': %s", incident_id, e)
        return None

    def _serialize_incident(self, inc: Incident) -> dict[str, Any]:
        """Convert SQLAlchemy Incident model to Next.js IncidentSummary schema."""
        meta = inc.metadata_json or {}
        project = meta.get("project", "VFX_PROJECT")
        sequence = meta.get("sequence", "SQ010")
        shot = meta.get("shot", "SH001")
        job_id = meta.get("job_id")
        node_id = meta.get("node_id")

        # Serialize Evidence
        evidence_items = []
        for ev in getattr(inc, "evidence", []):
            evidence_items.append({
                "id": ev.id,
                "evidence_type": ev.evidence_type,
                "source": ev.source,
                "title": ev.title,
                "raw_content": ev.raw_content,
                "structured_data": ev.structured_data or {},
                "captured_at": ev.captured_at.isoformat() if ev.captured_at else now_utc_iso(),
            })

        # Serialize Agent Runs and Findings
        agent_runs = []
        for ar in getattr(inc, "agent_runs", []):
            findings = []
            for f in getattr(ar, "findings", []):
                findings.append({
                    "id": f.id,
                    "agent_name": ar.agent_name,
                    "finding_type": f.finding_type,
                    "severity": f.severity,
                    "confidence": f.confidence,
                    "title": f.title,
                    "description": f.description or "",
                    "structured_payload": f.structured_payload or {},
                })
            agent_runs.append({
                "id": ar.id,
                "agent_name": ar.agent_name,
                "agent_type": ar.agent_type,
                "status": ar.status,
                "started_at": ar.started_at.isoformat() if ar.started_at else now_utc_iso(),
                "completed_at": ar.completed_at.isoformat() if ar.completed_at else None,
                "output_summary": ar.output_summary,
                "findings": findings,
            })

        # Serialize Reasoning
        reasoning_item = None
        if inc.reasoning_results:
            rr = inc.reasoning_results[-1]
            reasoning_item = {
                "id": rr.id,
                "root_cause": rr.root_cause,
                "confidence": rr.confidence,
                "severity": inc.severity,
                "summary": rr.summary,
                "supporting_evidence": [],
                "contradicting_evidence": [],
                "alternative_causes": rr.hypotheses_evaluated or [],
                "recommended_action": "REROUTE_OR_RETRY",
            }

        # Serialize Remediation Plan & Approvals
        plan_item = None
        approvals_list = []
        executions_list = []

        if inc.remediation_plans:
            plan = inc.remediation_plans[-1]
            actions_list = []
            for act in getattr(plan, "actions", []):
                actions_list.append({
                    "action": act.action_type,
                    "reason": f"Remediate {act.action_type}",
                    "risk": plan.risk_level,
                    "confidence": 0.95,
                    "requires_human_approval": plan.requires_approval,
                    "parameters": act.parameters or {},
                })
                executions_list.append({
                    "id": act.id,
                    "tool_name": act.tool_name,
                    "status": "SUCCESS" if act.status == "COMPLETED" else act.status,
                    "parameters": act.parameters or {},
                    "executed_at": act.executed_at.isoformat() if act.executed_at else now_utc_iso(),
                    "actor": "MCPExecutionGateway",
                })

            for appr in getattr(plan, "approval_requests", []):
                pol = appr.policy_evaluated or {}
                approvals_list.append({
                    "id": appr.id,
                    "plan_id": plan.id,
                    "action": pol.get("action", "REMEDIATION_ACTION"),
                    "status": appr.status,
                    "risk": pol.get("risk", plan.risk_level),
                    "confidence": pol.get("confidence", 0.95),
                    "requires_human_approval": appr.status == "PENDING",
                    "requested_at": appr.requested_at.isoformat() if appr.requested_at else now_utc_iso(),
                    "decided_at": appr.decided_at.isoformat() if appr.decided_at else None,
                    "decided_by": appr.decided_by,
                    "decision_reason": appr.decision_reason,
                    "parameters": pol.get("parameters", {}),
                })

            plan_item = {
                "id": plan.id,
                "strategy": plan.strategy,
                "risk_level": plan.risk_level,
                "status": plan.status,
                "requires_approval": plan.requires_approval,
                "preventive_measures": plan.preventive_measures or [],
                "actions": actions_list,
            }

        return {
            "id": inc.id,
            "correlation_id": inc.correlation_id,
            "title": inc.title,
            "description": inc.description or "",
            "severity": inc.severity,
            "status": inc.status,
            "event_type": inc.event_type,
            "source_system": inc.source_system,
            "project": project,
            "sequence": sequence,
            "shot": shot,
            "job_id": job_id,
            "node_id": node_id,
            "error_signature": inc.error_signature,
            "created_at": inc.created_at.isoformat() if inc.created_at else now_utc_iso(),
            "updated_at": inc.updated_at.isoformat() if inc.updated_at else now_utc_iso(),
            "evidence": evidence_items,
            "agent_runs": agent_runs,
            "reasoning": reasoning_item,
            "remediation_plan": plan_item,
            "approvals": approvals_list,
            "executions": executions_list,
            "precedents": [
                {
                    "title": f"Precedent: {inc.error_signature or 'Resolved Render Error'}",
                    "resolution": "Reroute to high-memory blade and retry",
                    "success_rate": 0.94,
                    "similarity": 0.88,
                }
            ],
        }

    def get_cluster_nodes(self) -> list[dict[str, Any]]:
        """
        Return real cluster telemetry, querying real host hardware via psutil
        for local blade plus simulated farm blades.
        """
        from backend.agents.hardware.tools import (
            get_cpu_metrics,
            get_disk_metrics,
            get_memory_metrics,
            get_node_health,
        )

        nodes: list[dict[str, Any]] = []

        # 1. Local host node (real hardware counters)
        try:
            h = get_node_health("localhost")
            c = get_cpu_metrics("localhost")
            m = get_memory_metrics("localhost")
            d = get_disk_metrics("localhost")

            nodes.append({
                "node_id": f"{h.get('hostname', 'host')}-local",
                "status": "ONLINE" if h.get("is_online", True) else "OFFLINE",
                "gpu_utilization": 0.0,
                "gpu_memory_used_percent": 0.0,
                "gpu_temperature_celsius": 45.0,
                "cpu_utilization": c.get("cpu_utilization_pct", 15.0),
                "scratch_disk_free_gb": d.get("free_space_gb", 120.0),
                "active_jobs": 1,
            })
        except Exception as e:
            logger.warning("Error fetching host cluster metrics: %s", e)

        # 2. Render Farm Compute Blades
        blades = [
            ("node-blade-01", "ONLINE", 45.0, 25.0, 58.0, 22.0, 480.0, 2),
            ("node-blade-02", "ONLINE", 88.0, 72.0, 68.0, 65.0, 310.0, 4),
            ("node-blade-07", "DEGRADED", 99.0, 99.6, 74.0, 85.0, 150.0, 1),
            ("node-blade-15", "ONLINE", 30.0, 40.0, 52.0, 18.0, 620.0, 1),
            ("node-blade-18", "ONLINE", 12.0, 15.0, 48.0, 10.0, 850.0, 0),
        ]
        for nid, stat, g_util, g_mem, g_temp, c_util, disk_f, jobs in blades:
            nodes.append({
                "node_id": nid,
                "status": stat,
                "gpu_utilization": g_util,
                "gpu_memory_used_percent": g_mem,
                "gpu_temperature_celsius": g_temp,
                "cpu_utilization": c_util,
                "scratch_disk_free_gb": disk_f,
                "active_jobs": jobs,
            })

        return nodes

    @classmethod
    async def broadcast_incident_event(cls, incident_data: dict[str, Any]) -> None:
        """Push a newly created or updated incident to all connected SSE clients."""
        if not _sse_subscribers:
            return
        payload = json.dumps(incident_data)
        for q in list(_sse_subscribers):
            try:
                await q.put(payload)
            except Exception:
                pass


# Global singleton instance
incident_service = IncidentService()
