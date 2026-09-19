"""
End-to-End Simulation Pipeline Runner.
Orchestrates execution of the actual real platform pipeline:
Simulation Event
      ↓
Event Ingestion & Normalizer (backend/events/)
      ↓
Redis Stream
      ↓
Supervisor Agent (backend/agents/supervisor/)
      ↓
Specialist Agents (Render QA, Hardware, Asset Validation, Historical)
      ↓
Gemini Reasoning Engine (backend/reasoning/)
      ↓
Remediation Strategy Specialist (backend/remediation/)
      ↓
Policy Engine (backend/governance/)
      ↓
Human / Auto Approval Gate
      ↓
MCP Execution Gateway (backend/mcp/)
      ↓
IBM watsonx Workflow Adapter (backend/integrations/watsonx/)
      ↓
Audit Log & Traceability
"""

from datetime import datetime, timezone
import logging
from typing import Any, Optional
import httpx

from backend.agents.supervisor.schemas import InvestigationRequest
from backend.agents.supervisor.supervisor_agent import SupervisorAgent
from backend.common.logging import (
    agent_run_id_ctx,
    approval_id_ctx,
    correlation_id_ctx,
    event_id_ctx,
    incident_id_ctx,
    mcp_execution_id_ctx,
    reasoning_id_ctx,
    remediation_id_ctx,
)
from backend.events.service import EventIngestionService
from backend.governance.policy_engine import PolicyEngine
from backend.governance.service import GovernanceService
from backend.mcp.schemas import MCPExecutionContext
from backend.mcp.server import MCPServer
from backend.reasoning.engine import RootCauseReasoningEngine
from backend.reasoning.schemas import ReasoningContextInput
from backend.remediation.strategy_agent import RemediationStrategyAgent
from simulations.scenarios import get_scenario_event

logger = logging.getLogger("vfx.simulations.runner")


class SimulationPipelineRunner:
    """
    Executes the entire end-to-end incident investigation and remediation pipeline
    without using mock shortcuts or fake UI updates.
    """

    def __init__(
        self,
        ingestion_service: Optional[EventIngestionService] = None,
        supervisor: Optional[SupervisorAgent] = None,
        reasoning_engine: Optional[RootCauseReasoningEngine] = None,
        remediation_agent: Optional[RemediationStrategyAgent] = None,
        governance_svc: Optional[GovernanceService] = None,
        mcp_server_instance: Optional[MCPServer] = None,
    ) -> None:
        self.ingestion = ingestion_service or EventIngestionService()
        self.supervisor = supervisor or SupervisorAgent()
        self.reasoning = reasoning_engine or RootCauseReasoningEngine()
        self.remediation = remediation_agent or RemediationStrategyAgent()
        self.governance = governance_svc or GovernanceService(policy_engine=PolicyEngine())
        self.mcp = mcp_server_instance or MCPServer(governance_svc=self.governance)

    async def run(
        self,
        scenario_name: str,
        seed: Optional[int] = None,
        target_api_url: Optional[str] = None,
        auto_approve_human_gate: bool = True,
        raw_event_override: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Execute the complete architecture pipeline for the given failure scenario.
        """
        timeline: list[dict[str, Any]] = []

        def log_stage(stage: str, details: Any):
            entry = {
                "stage": stage,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": details,
            }
            timeline.append(entry)
            logger.info("Pipeline Stage [%s]: %s", stage, details)

        # 1. Generate Realistic Scenario Event with optional seed (or use override)
        raw_event = raw_event_override or get_scenario_event(scenario_name, seed=seed)
        log_stage("1_SIMULATION_EVENT_GENERATED", {
            "scenario": scenario_name,
            "seed": seed,
            "event_type": raw_event.get("event_type"),
            "source": raw_event.get("source"),
            "project": raw_event.get("project"),
            "shot": raw_event.get("shot"),
        })

        # 2. Ingestion & Normalization
        if target_api_url:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(target_api_url, json=raw_event)
                ingest_resp = resp.json()
                log_stage("2_HTTP_EVENT_INGESTED", {"status_code": resp.status_code, "response": ingest_resp})
                # If target API is used, normalize locally for subsequent stages
                normalized_event = self.ingestion.normalizer.normalize(raw_event)
        else:
            ingestion_result = await self.ingestion.ingest_event(raw_event)
            normalized_event = ingestion_result.normalized_event
            log_stage("2_EVENT_NORMALIZED", {
                "event_id": ingestion_result.event_id,
                "correlation_id": ingestion_result.correlation_id,
                "idempotency_key": ingestion_result.idempotency_key,
                "status": ingestion_result.status,
            })

        if not normalized_event:
            raise RuntimeError("Failed to normalize event in ingestion pipeline.")

        incident_id = f"inc-{normalized_event.correlation_id[:8]}"

        # Propagate distributed tracing context
        correlation_id_ctx.set(normalized_event.correlation_id)
        event_id_ctx.set(normalized_event.event_id)
        incident_id_ctx.set(incident_id)

        # 3. Google ADK Supervisor Agent Investigation
        investigation_req = InvestigationRequest(
            incident_id=incident_id,
            event=normalized_event.model_dump(mode="json"),
        )
        agent_run_id = f"run-sup-{normalized_event.correlation_id[:8]}"
        agent_run_id_ctx.set(agent_run_id)

        investigation_result = await self.supervisor.investigate_incident(investigation_req)
        log_stage("3_SUPERVISOR_INVESTIGATION_COMPLETE", {
            "incident_id": investigation_result.incident_id,
            "specialists_invoked": len(investigation_result.findings),
            "evidence_count": len(investigation_result.evidence),
            "confidence": investigation_result.confidence,
        })

        # 4. Root Cause Reasoning Engine (Gemini ADK)
        # Separate findings by agent type
        render_qa_f = [f.model_dump() for f in investigation_result.findings if "RenderQA" in f.agent_name or "QA" in f.finding_type]
        hw_f = [f.model_dump() for f in investigation_result.findings if "Hardware" in f.agent_name or "GPU" in f.finding_type or "NODE" in f.finding_type]
        asset_f = [f.model_dump() for f in investigation_result.findings if "Asset" in f.agent_name or "USD" in f.finding_type or "ASSET" in f.finding_type]
        if not (render_qa_f or hw_f or asset_f):
            render_qa_f = [f.model_dump() for f in investigation_result.findings]

        reasoning_input = ReasoningContextInput(
            incident=normalized_event.model_dump(mode="json"),
            render_qa_findings=render_qa_f,
            hardware_findings=hw_f,
            asset_findings=asset_f,
            historical_evidence={"similar_incidents": [e.structured_data for e in investigation_result.evidence if e.evidence_type == "HISTORICAL_PRECEDENT"]},
        )
        reasoning_result = self.reasoning.analyze(reasoning_input)
        reasoning_id = getattr(reasoning_result, "id", f"rsn-{normalized_event.correlation_id[:8]}")
        reasoning_id_ctx.set(reasoning_id)

        log_stage("4_GEMINI_REASONING_SYNTHESIZED", {
            "root_cause": reasoning_result.root_cause,
            "confidence": reasoning_result.confidence,
            "severity": reasoning_result.severity,
            "recommended_action": reasoning_result.recommended_action,
        })

        # 5. Remediation Strategy Specialist
        remediation_context = {
            "root_cause_analysis": reasoning_result.model_dump(mode="json"),
            "evidence": [e.title for e in investigation_result.evidence],
            "confidence": reasoning_result.confidence,
            "incident_severity": reasoning_result.severity,
            "incident_id": incident_id,
            "job_id": normalized_event.entity.job_id,
            "shot_id": normalized_event.entity.shot,
            "node_id": normalized_event.entity.node_id,
            "project": normalized_event.entity.project,
        }
        remediation_plan = self.remediation.propose_plan(remediation_context)
        remediation_id_ctx.set(remediation_plan.plan_id)

        log_stage("5_REMEDIATION_PLAN_PROPOSED", {
            "plan_id": remediation_plan.plan_id,
            "actions_proposed": len(remediation_plan.actions),
            "overall_risk": remediation_plan.overall_risk,
            "requires_human_approval": remediation_plan.requires_human_approval,
        })

        # 6. Policy Gate & Governance Approval
        created_approvals = []
        for action in remediation_plan.actions:
            appr = self.governance.create_approval_request(
                action=action.model_dump(),
                incident_id=incident_id,
                plan_id=remediation_plan.plan_id,
                incident_severity=reasoning_result.severity,
            )
            approval_id_ctx.set(appr.approval_id)
            # If requires human approval and auto_approve_human_gate is enabled for test runner
            if appr.status == "PENDING" and auto_approve_human_gate:
                appr = self.governance.approve_action(
                    approval_id=appr.approval_id,
                    actor="simulation_lead_supervisor",
                    notes="Approved via deterministic simulation test harness",
                )
            created_approvals.append(appr)

        log_stage("6_GOVERNANCE_EVALUATED", {
            "total_approvals": len(created_approvals),
            "statuses": [a.status for a in created_approvals],
        })

        # 7. MCP Execution Gateway & IBM watsonx Workflow Adapter
        executed_mcp_actions = []
        for appr in created_approvals:
            if appr.status in ("APPROVED", "AUTO_APPROVED"):
                approval_id_ctx.set(appr.approval_id)
                context = MCPExecutionContext(
                    approval_id=appr.approval_id,
                    actor="simulation_runner",
                    incident_id=incident_id,
                    plan_id=remediation_plan.plan_id,
                )
                # Map remediation action to tool name
                tool_name = action_to_tool_name(appr.action_name)
                # Normalize action parameters for strict MCP tool schema
                tool_params = build_mcp_tool_parameters(
                    tool_name=tool_name,
                    raw_params=appr.parameters,
                    incident_id=incident_id,
                    normalized_event=normalized_event,
                    reasoning_result=reasoning_result,
                )
                mcp_resp = self.mcp.call_tool(
                    tool_name=tool_name,
                    parameters=tool_params,
                    context=context,
                )
                if mcp_resp.execution_id:
                    mcp_execution_id_ctx.set(mcp_resp.execution_id)
                executed_mcp_actions.append(mcp_resp)

        log_stage("7_MCP_WATSONX_EXECUTIONS_COMPLETE", {
            "executed_count": len(executed_mcp_actions),
            "all_success": all(e.success for e in executed_mcp_actions) if executed_mcp_actions else True,
        })

        # 8. Resolution Status Determination
        has_failed_mcp = any(not e.success for e in executed_mcp_actions)
        all_mcp_success = bool(executed_mcp_actions) and all(e.success for e in executed_mcp_actions)

        if all_mcp_success:
            incident_status = "RESOLVED"
            resolution_summary = f"Incident successfully remediated via {len(executed_mcp_actions)} approved actions for root cause {reasoning_result.root_cause}."
        elif has_failed_mcp:
            incident_status = "UNRESOLVED"
            resolution_summary = "Remediation action failed during execution; incident remains open for TD review."
        elif reasoning_result.root_cause == "INSUFFICIENT_EVIDENCE":
            incident_status = "INVESTIGATING"
            resolution_summary = "Insufficient evidence to determine root cause; assigned for manual investigation."
        elif investigation_result.conflicts:
            incident_status = "AWAITING_HUMAN_REVIEW"
            resolution_summary = "Conflicting findings detected across specialist agents; queued for human supervisor adjudication."
        else:
            incident_status = "IN_PROGRESS"
            resolution_summary = "Investigation completed; awaiting governance or execution."

        log_stage("8_INCIDENT_STATUS_FINALIZED", {
            "incident_id": incident_id,
            "status": incident_status,
            "resolution_summary": resolution_summary,
        })

        return {
            "success": True,
            "scenario": scenario_name,
            "seed": seed,
            "incident_id": incident_id,
            "status": incident_status,
            "resolution_summary": resolution_summary,
            "normalized_event": normalized_event.model_dump(mode="json"),
            "investigation": investigation_result.model_dump(mode="json"),
            "conflicts": [c.model_dump() for c in investigation_result.conflicts],
            "reasoning": reasoning_result.model_dump(mode="json"),
            "remediation_plan": remediation_plan.model_dump(mode="json"),
            "approvals": [a.model_dump() for a in created_approvals],
            "mcp_executions": [e.model_dump() for e in executed_mcp_actions],
            "audit_records": self.mcp.gateway.audit_records,
            "timeline": timeline,
        }


def action_to_tool_name(action_name: str) -> str:
    """Map action type string to MCP tool name."""
    mapping = {
        "RETRY_JOB": "retry_render_job",
        "RETRY_RENDER_JOB": "retry_render_job",
        "ASSIGN_PIPELINE_TD": "assign_pipeline_td",
        "UPDATE_SHOT_STATUS": "update_shot_status",
        "CREATE_INCIDENT": "create_incident",
        "NOTIFY_TEAM": "notify_team",
        "GENERATE_POSTMORTEM": "generate_postmortem",
        "GET_JOB_STATUS": "get_job_status",
        "GET_NODE_HEALTH": "get_node_health",
    }
    return mapping.get(action_name.upper(), action_name.lower())


def build_mcp_tool_parameters(
    tool_name: str,
    raw_params: dict[str, Any],
    incident_id: str,
    normalized_event: Any,
    reasoning_result: Any,
) -> dict[str, Any]:
    """
    Adapts high-level remediation action parameters into the strict Pydantic schemas
    required by each controlled MCP tool.
    """
    entity = normalized_event.entity
    project = entity.project or "DUNE_PART_3"
    seq = entity.sequence or "SQ010"
    shot = entity.shot or "SH0120"
    job_id = entity.job_id or raw_params.get("job_id", f"job-{incident_id[:8]}")
    node_id = entity.node_id or raw_params.get("node_id", "node-blade-01")

    if tool_name == "retry_render_job":
        return {
            "job_id": raw_params.get("job_id", job_id),
            "node_class": raw_params.get("target_pool", raw_params.get("node_class", "standard")),
            "priority_boost": int(raw_params.get("priority_boost", 10)),
            "frame_range": raw_params.get("frame_range", None),
            "excluded_nodes": [raw_params["previous_node"]] if "previous_node" in raw_params else raw_params.get("excluded_nodes", []),
        }

    elif tool_name == "notify_team":
        channel = raw_params.get("channel", "#pipeline-alerts")
        if not channel.startswith("#"):
            channel = f"#{channel}"
        msg = raw_params.get("message") or f"Alert for job {job_id} ({incident_id}): {reasoning_result.root_cause}"
        return {
            "channel": channel,
            "message": msg,
            "urgency": "high" if str(raw_params.get("severity", "")).upper() in ("HIGH", "CRITICAL") else "normal",
            "mentions": raw_params.get("mentions", ["pipeline_td_lead"]),
            "thread_id": None,
        }

    elif tool_name == "update_shot_status":
        status_val = raw_params.get("status", raw_params.get("new_status", "hold")).lower()
        valid_status = "on_hold" if "hold" in status_val or "asset" in status_val else "ip"
        return {
            "project": project,
            "sequence": seq,
            "shot": raw_params.get("shot_id", shot),
            "new_status": valid_status,
            "notes": f"Status updated automatically during remediation for incident {incident_id}",
            "updated_by": "SimulationPipelineRunner",
        }

    elif tool_name == "assign_pipeline_td":
        return {
            "incident_id": incident_id,
            "td_name": raw_params.get("role", raw_params.get("td_name", "alex.vfx.td")),
            "priority": "high" if str(reasoning_result.severity).upper() in ("HIGH", "CRITICAL") else "medium",
            "department": "lighting" if "LIGHTING" in str(raw_params) else "pipeline",
            "notes": f"Assigned for {reasoning_result.root_cause} mitigation.",
        }

    elif tool_name == "create_incident":
        return {
            "title": f"Incident {incident_id}: {reasoning_result.root_cause}",
            "description": f"Automated simulation generated for {normalized_event.event_type}",
            "severity": str(reasoning_result.severity).lower(),
            "category": "render",
            "related_incident_id": incident_id,
            "assignee": "on_call_td",
            "labels": ["simulation", normalized_event.event_type.lower()],
        }

    elif tool_name == "generate_postmortem":
        return {
            "incident_id": incident_id,
            "title": f"Postmortem: {reasoning_result.root_cause} on {job_id}",
            "root_cause": reasoning_result.root_cause,
            "summary": f"Incident triggered on {job_id} on shot {shot}. Analyzed with {int(reasoning_result.confidence*100)}% confidence.",
            "timeline": [{"event": "Ingested", "timestamp": normalized_event.timestamp.isoformat()}],
            "preventive_measures": [f"Adjust render pool settings to accommodate {reasoning_result.root_cause} workload."],
        }

    elif tool_name == "get_job_status":
        return {"job_id": raw_params.get("job_id", job_id)}

    elif tool_name == "get_node_health":
        return {"node_id": raw_params.get("node_id", node_id)}

    return raw_params
