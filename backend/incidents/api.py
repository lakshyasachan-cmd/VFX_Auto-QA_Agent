"""
FastAPI router for Incident Management, Cluster Telemetry, and Real-Time SSE Streaming.
Mounted at /api/v1/incidents and /api/v1/cluster.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from backend.incidents.service import (
    _sse_subscribers,
    incident_service,
)

logger = logging.getLogger("vfx.incidents.api")

router = APIRouter(prefix="/api/v1", tags=["Incidents & Mission Control"])


@router.get(
    "/incidents",
    summary="List all VFX incidents",
    description="Retrieve live incidents from PostgreSQL database for the Mission Control dashboard.",
)
async def list_incidents(
    status: Optional[str] = Query(None, description="Filter by status (OPEN, INVESTIGATING, AWAITING_APPROVAL, RESOLVED)"),
    severity: Optional[str] = Query(None, description="Filter by severity (CRITICAL, HIGH, MEDIUM, LOW)"),
    limit: int = Query(50, ge=1, le=200, description="Max number of incidents to return"),
) -> list[dict[str, Any]]:
    return incident_service.list_incidents(status=status, severity=severity, limit=limit)


@router.get(
    "/incidents/{incident_id}",
    summary="Get detailed incident investigation graph",
    description="Returns full incident details including multi-agent traces, epistemic findings, and reasoning.",
)
async def get_incident(incident_id: str) -> dict[str, Any]:
    incident = incident_service.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )
    return incident


@router.get(
    "/incidents/stream/live",
    summary="Real-time incident event stream (SSE)",
    description="Streams newly created or updated incidents to the dashboard via Server-Sent Events.",
)
async def stream_incidents(request: Request):
    """Server-Sent Events endpoint streaming live incidents to the Next.js UI."""
    queue: asyncio.Queue = asyncio.Queue()
    _sse_subscribers.append(queue)

    async def event_generator():
        try:
            # Send initial connection notice
            init_payload = json.dumps({"event": "CONNECTED", "timestamp": datetime.now(timezone.utc).isoformat()})
            yield f"data: {init_payload}\n\n"

            while True:
                # Check for client disconnect
                if await request.is_disconnected():
                    break

                try:
                    # Wait for next incident event with a 5-second heartbeat
                    data = await asyncio.wait_for(queue.get(), timeout=5.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat comment to keep connection alive
                    yield ": ping\n\n"
        finally:
            if queue in _sse_subscribers:
                _sse_subscribers.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/cluster/nodes",
    summary="Get render cluster node health",
    description="Returns live compute blade telemetry (CPU, RAM, disk, GPU utilization).",
)
async def get_cluster_nodes() -> list[dict[str, Any]]:
    return incident_service.get_cluster_nodes()


@router.post(
    "/incidents/trigger",
    summary="Trigger a VFX failure scenario simulation",
    description="Creates a realistic incident from the selected scenario and streams it live to the dashboard.",
)
async def trigger_simulation_incident(
    scenario: str = Query("gpu_oom", description="Scenario: gpu_oom | missing_frames | corrupted_alembic | node_thermal"),
    background_tasks: BackgroundTasks = None,
) -> dict[str, Any]:
    """
    Creates a new VFX incident from a built-in scenario template, persists it to
    PostgreSQL, and pushes it to all connected SSE dashboard clients immediately.
    """
    import uuid
    from datetime import datetime, timezone
    from backend.database.models.incident import Incident, IncidentEvidence
    from backend.database.models.agent import AgentRun, AgentFinding, ReasoningResult
    from backend.database.models.remediation import RemediationPlan, Action, ApprovalRequest
    from backend.database.session import SessionLocal

    # ── Scenario templates ────────────────────────────────────────────────────
    SCENARIOS = {
        "gpu_oom": {
            "title": "Arnold GPU Out-Of-Memory (Exit 137)",
            "description": "Render task failed on node-blade-07 with CUDA OOM while allocating 4096MB buffer during beauty render.",
            "severity": "CRITICAL",
            "status": "AWAITING_APPROVAL",
            "event_type": "RENDER_JOB_FAILED",
            "source_system": "deadline",
            "error_signature": "GPU_OUT_OF_MEMORY",
            "project": "SOLARIS_VFX", "sequence": "SQ030", "shot": "SH0340",
            "job_id": "job-arnold-" + uuid.uuid4().hex[:6],
            "node_id": "node-blade-07",
            "evidence": [
                {"evidence_type": "RENDER_LOG", "source": "deadline",
                 "title": "Deadline Slave Stderr Log",
                 "raw_content": "00:02:00 24576MB ERROR | [gpu] CUDA error: Out of memory while allocating 4096MB buffer.\nProcess exit code: 137",
                 "structured_data": {"exit_code": 137, "vram_peak_mb": 24576}},
            ],
            "root_cause": "GPU_VRAM_EXHAUSTION",
            "root_cause_summary": "Frame failed due to Arnold VRAM exhaustion on node-blade-07. Rerouting to 48GB GPU pool required.",
            "risk_level": "MEDIUM",
            "requires_approval": True,
            "actions": [
                {"action": "RETRY_JOB", "risk": "MEDIUM", "confidence": 0.95,
                 "requires_human_approval": True,
                 "parameters": {"target_pool": "gpu_48gb", "priority_boost": 15}},
                {"action": "NOTIFY_TEAM", "risk": "LOW", "confidence": 0.99,
                 "requires_human_approval": False,
                 "parameters": {"channel": "#lighting-tds", "message": "Frame rerouted to 48GB pool."}},
            ],
        },
        "missing_frames": {
            "title": "V-Ray Dropped Frames in Sequence",
            "description": "4 missing EXR output files (frames 1012-1015) after queue dispatcher timeout.",
            "severity": "HIGH",
            "status": "INVESTIGATING",
            "event_type": "RENDER_JOB_FAILED",
            "source_system": "deadline",
            "error_signature": "MISSING_OUTPUT_FRAMES",
            "project": "DUNE_PART_3", "sequence": "SQ020", "shot": "SH0010",
            "job_id": "job-vray-" + uuid.uuid4().hex[:6],
            "node_id": "render-node-15",
            "evidence": [
                {"evidence_type": "FRAME_QC", "source": "storage_audit",
                 "title": "Farm Output Directory Scan",
                 "raw_content": "Missing frames in sequence: [1012, 1013, 1014, 1015]",
                 "structured_data": {"missing_frames": [1012, 1013, 1014, 1015]}},
            ],
            "root_cause": "DISPATCHER_TASK_DROP",
            "root_cause_summary": "Frames 1012-1015 were dropped during batch submission to the farm queue.",
            "risk_level": "LOW",
            "requires_approval": False,
            "actions": [
                {"action": "RETRY_JOB", "risk": "LOW", "confidence": 0.95,
                 "requires_human_approval": False,
                 "parameters": {"frame_range": "1012-1015"}},
            ],
        },
        "corrupted_alembic": {
            "title": "Corrupted Alembic Point Cache — FX Asset Load Failure",
            "description": "Houdini FX cache read failed: alembic geometry cache reported checksum mismatch on SAN path.",
            "severity": "HIGH",
            "status": "INVESTIGATING",
            "event_type": "ASSET_VALIDATION_FAILED",
            "source_system": "asset_storage",
            "error_signature": "CORRUPTED_ASSET_DATA",
            "project": "AVATAR_3", "sequence": "SQ090", "shot": "SH0200",
            "job_id": "job-houdini-" + uuid.uuid4().hex[:6],
            "node_id": "node-blade-18",
            "evidence": [
                {"evidence_type": "ASSET_VALIDATION", "source": "asset_storage",
                 "title": "Alembic Cache Integrity Check",
                 "raw_content": "ERROR: abc_checksum_mismatch on /jobs/AVATAR_3/SQ090/SH0200/fx/ocean_splash_v012.abc\nExpected: e3b0c44298, Got: 1a2b3c4d5e",
                 "structured_data": {"corrupted_path": "ocean_splash_v012.abc", "error": "checksum_mismatch"}},
            ],
            "root_cause": "CORRUPTED_ASSET_DATA",
            "root_cause_summary": "Alembic point cache corrupt on SAN. Re-simulation from USD source or restore from backup required.",
            "risk_level": "HIGH",
            "requires_approval": True,
            "actions": [
                {"action": "UPDATE_SHOT_STATUS", "risk": "HIGH", "confidence": 0.92,
                 "requires_human_approval": True,
                 "parameters": {"shot": "SH0200", "new_status": "blocked", "notes": "Awaiting FX cache re-sim"}},
            ],
        },
        "node_thermal": {
            "title": "Render Blade Thermal Throttle — GPU at 93°C",
            "description": "GPU driver reporting thermal slowdown on node-blade-07; 4 consecutive frame timeouts in past 20 min.",
            "severity": "CRITICAL",
            "status": "REMEDIATING",
            "event_type": "NODE_UNHEALTHY",
            "source_system": "tractor",
            "error_signature": "THERMAL_THROTTLE_GPU_OVERHEAT",
            "project": "DUNE_PART_3", "sequence": "SQ020", "shot": "SH0090",
            "job_id": None,
            "node_id": "node-blade-07",
            "evidence": [
                {"evidence_type": "NODE_TELEMETRY", "source": "ipmi",
                 "title": "Blade GPU Temperature Alert",
                 "raw_content": "ALERT: GPU0 temp 93.4°C exceeds 90°C threshold. Clock frequencies throttled to 67%.",
                 "structured_data": {"gpu_temp_c": 93.4, "throttle_pct": 67, "node": "node-blade-07"}},
            ],
            "root_cause": "GPU_THERMAL_THROTTLE",
            "root_cause_summary": "Blade cooling failure causing GPU throttle. Node should be drained and taken offline for maintenance.",
            "risk_level": "HIGH",
            "requires_approval": True,
            "actions": [
                {"action": "NOTIFY_TEAM", "risk": "LOW", "confidence": 0.99,
                 "requires_human_approval": False,
                 "parameters": {"channel": "#render-ops", "message": "node-blade-07 thermal throttle at 93°C. Draining jobs."}},
            ],
        },
    }

    tmpl = SCENARIOS.get(scenario, SCENARIOS["gpu_oom"])
    inc_id = "inc-" + uuid.uuid4().hex[:8] + "-" + scenario.replace("_", "-")
    now = datetime.now(timezone.utc)

    try:
        with SessionLocal() as db:
            # 1. Create Incident
            inc = Incident(
                id=inc_id,
                correlation_id=str(uuid.uuid4()),
                title=tmpl["title"],
                description=tmpl["description"],
                severity=tmpl["severity"],
                status=tmpl["status"],
                event_type=tmpl["event_type"],
                source_system=tmpl["source_system"],
                error_signature=tmpl["error_signature"],
                metadata_json={
                    "project": tmpl["project"], "sequence": tmpl["sequence"],
                    "shot": tmpl["shot"], "job_id": tmpl.get("job_id"),
                    "node_id": tmpl["node_id"],
                },
                created_at=now,
            )
            db.add(inc)
            db.flush()

            # 2. Add Evidence
            for ev in tmpl["evidence"]:
                db.add(IncidentEvidence(
                    incident_id=inc.id,
                    evidence_type=ev["evidence_type"],
                    source=ev["source"],
                    title=ev["title"],
                    raw_content=ev.get("raw_content"),
                    structured_data=ev.get("structured_data", {}),
                    captured_at=now,
                ))

            # 3. Agent Run + Finding
            run = AgentRun(
                incident_id=inc.id,
                agent_name="SupervisorAgent",
                agent_type="SUPERVISOR",
                status="COMPLETED",
                started_at=now,
                completed_at=now,
                output_summary=f"Scenario '{scenario}' dispatched and triaged by supervisor.",
            )
            db.add(run)
            db.flush()
            db.add(AgentFinding(
                agent_run_id=run.id,
                finding_type=tmpl["error_signature"],
                severity=tmpl["severity"],
                confidence=0.96,
                title=tmpl["title"],
                description=tmpl["root_cause_summary"],
                structured_payload={},
            ))

            # 4. Reasoning Result
            rr = ReasoningResult(
                incident_id=inc.id,
                root_cause=tmpl["root_cause"],
                confidence=0.95,
                summary=tmpl["root_cause_summary"],
                hypotheses_evaluated=[],
                evidence_refs=[],
            )
            db.add(rr)
            db.flush()

            # 5. Remediation Plan, Actions, Approval Requests
            plan = RemediationPlan(
                incident_id=inc.id,
                reasoning_result_id=rr.id,
                strategy=f"Automated remediation for scenario: {scenario}",
                risk_level=tmpl["risk_level"],
                requires_approval=tmpl["requires_approval"],
            )
            db.add(plan)
            db.flush()

            for a in tmpl["actions"]:
                act = Action(
                    plan_id=plan.id,
                    action_type=a["action"],
                    tool_name=a["action"].lower(),
                    parameters=a.get("parameters", {}),
                    status="PENDING",
                )
                db.add(act)
                db.add(ApprovalRequest(
                    plan_id=plan.id,
                    status="PENDING" if a["requires_human_approval"] else "AUTO_APPROVED",
                    requested_at=now,
                    policy_evaluated={"action": a["action"], "risk": a["risk"], "confidence": a["confidence"]},
                ))

            db.commit()
            logger.info("Simulation incident '%s' created for scenario '%s'", inc_id, scenario)

        # 6. Broadcast to SSE subscribers
        inc_data = incident_service.get_incident(inc_id)
        if inc_data:
            await incident_service.broadcast_incident_event(inc_data)

        return {
            "success": True,
            "incident_id": inc_id,
            "scenario": scenario,
            "message": f"Incident '{tmpl['title']}' created and broadcast to dashboard.",
        }

    except Exception as e:
        logger.error("Failed to create simulation incident: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")

