"""
WatsonxWorkflowAdapter translating VFX workflow actions into IBM watsonx Orchestrate executions.
Supports mock mode (WATSONX_MOCK=true) without external network calls,
and live mode using WatsonxOrchestrateClient with structured logging and audit events.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Optional
import uuid

from backend.database.models.audit import AuditLog
from backend.database.session import SessionLocal
from backend.integrations.watsonx.client import WatsonxOrchestrateClient
from backend.integrations.watsonx.config import WatsonxSettings
from backend.integrations.watsonx.errors import WatsonxError
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.mcp.schemas import (
        AssignPipelineTDParams,
        CreateIncidentParams,
        GeneratePostmortemParams,
        GetJobStatusParams,
        GetNodeHealthParams,
        NotifyTeamParams,
        RetryRenderJobParams,
        UpdateShotStatusParams,
    )

logger = logging.getLogger("vfx.integrations.watsonx.adapter")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_utc_dt() -> datetime:
    return datetime.now(timezone.utc)


class WatsonxWorkflowAdapter:
    """
    Adapter interfacing between MCP Tool execution and IBM watsonx Orchestrate workflows.
    Ensures policy enforcement invariant: watsonx is an execution engine downstream of policy.
    """

    def __init__(
        self,
        settings: Optional[WatsonxSettings] = None,
        client: Optional[WatsonxOrchestrateClient] = None,
    ) -> None:
        self.settings = settings or WatsonxSettings.load_from_env()
        self.client = client or WatsonxOrchestrateClient(settings=self.settings)
        self.audit_records: list[dict[str, Any]] = []

    def _record_audit(
        self,
        workflow_name: str,
        parameters: dict[str, Any],
        status: str,
        result: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
        actor: str = "watsonx_workflow_adapter",
    ) -> str:
        """Record an immutable audit log entry for the watsonx workflow execution."""
        audit_id = str(uuid.uuid4())
        record = {
            "id": audit_id,
            "entity_type": "WatsonxWorkflowExecution",
            "entity_id": audit_id,
            "action": f"WATSONX_{status.upper()}",
            "workflow_name": workflow_name,
            "actor": actor,
            "parameters": parameters,
            "result": result or {},
            "error": error,
            "mock_mode": self.settings.mock_mode,
            "timestamp": now_utc_iso(),
        }
        self.audit_records.append(record)

        # Persist to database if available
        try:
            with SessionLocal() as session:
                log_entry = AuditLog(
                    id=audit_id,
                    entity_type="WatsonxWorkflowExecution",
                    entity_id=audit_id,
                    action=f"WATSONX_{status.upper()}",
                    actor=actor,
                    previous_state={"workflow_name": workflow_name, "mock_mode": self.settings.mock_mode},
                    new_state={"status": status, "result": result, "error": error},
                    details={"parameters": parameters, "workflow_name": workflow_name},
                    timestamp=now_utc_dt(),
                )
                session.add(log_entry)
                session.commit()
        except Exception as exc:
            logger.debug("Database audit record skipped: %s", exc)

        return audit_id

    # ─────────────────────────────────────────────────────────────
    # 1. retry_render_job
    # ─────────────────────────────────────────────────────────────
    def retry_render_job(self, params: RetryRenderJobParams) -> dict[str, Any]:
        """
        Execute or mock the watsonx workflow to resubmit/retry a render job.
        Required contract:
        {
          "success": true,
          "job_id": "...",
          "new_node": "...",
          "status": "QUEUED"
        }
        """
        node_class = params.node_class or "standard"
        param_dict = params.model_dump()

        if self.settings.mock_mode:
            logger.info("watsonx mock mode: simulating retry_render_job for %s", params.job_id)
            new_node = f"node-{node_class}-{uuid.uuid4().hex[:6]}"
            result = {
                "success": True,
                "job_id": params.job_id,
                "new_node": new_node,
                "status": "QUEUED",
                "node_class": node_class,
                "priority_boost": params.priority_boost or 0,
                "frame_range": params.frame_range or "all_failed",
                "submitted_at": now_utc_iso(),
            }
            self._record_audit("retry_render_job", param_dict, "SUCCESS", result=result)
            return result

        # Live mode: invoke IBM watsonx Orchestrate skill
        try:
            resp = self.client.run_workflow("retry_render_job_skill", param_dict)
            output = resp.get("outputs", {})
            result = {
                "success": True,
                "job_id": output.get("job_id", params.job_id),
                "new_node": output.get("new_node", f"node-{node_class}-assigned"),
                "status": output.get("status", "QUEUED"),
                "submitted_at": now_utc_iso(),
            }
            self._record_audit("retry_render_job", param_dict, "SUCCESS", result=result)
            return result
        except WatsonxError as exc:
            self._record_audit("retry_render_job", param_dict, "FAILED", error=str(exc))
            raise

    # ─────────────────────────────────────────────────────────────
    # 2. assign_pipeline_td
    # ─────────────────────────────────────────────────────────────
    def assign_pipeline_td(self, params: AssignPipelineTDParams) -> dict[str, Any]:
        """Assign Pipeline TD via watsonx Orchestrate."""
        param_dict = params.model_dump()

        if self.settings.mock_mode:
            logger.info("watsonx mock mode: simulating assign_pipeline_td for %s", params.td_name)
            result = {
                "success": True,
                "assignment_id": f"asgn-{uuid.uuid4().hex[:8]}",
                "incident_id": params.incident_id,
                "td_name": params.td_name,
                "department": params.department,
                "priority": params.priority,
                "status": "ASSIGNED",
                "assigned_at": now_utc_iso(),
                "notes": params.notes,
            }
            self._record_audit("assign_pipeline_td", param_dict, "SUCCESS", result=result)
            return result

        try:
            resp = self.client.run_workflow("assign_pipeline_td_skill", param_dict)
            output = resp.get("outputs", {})
            result = {
                "success": True,
                "assignment_id": output.get("assignment_id", f"asgn-{uuid.uuid4().hex[:8]}"),
                "incident_id": params.incident_id,
                "td_name": params.td_name,
                "department": params.department,
                "priority": params.priority,
                "status": "ASSIGNED",
                "assigned_at": now_utc_iso(),
                "notes": params.notes,
            }
            self._record_audit("assign_pipeline_td", param_dict, "SUCCESS", result=result)
            return result
        except WatsonxError as exc:
            self._record_audit("assign_pipeline_td", param_dict, "FAILED", error=str(exc))
            raise

    # ─────────────────────────────────────────────────────────────
    # 3. update_shot_status
    # ─────────────────────────────────────────────────────────────
    def update_shot_status(self, params: UpdateShotStatusParams) -> dict[str, Any]:
        """Update shot status via watsonx Orchestrate."""
        param_dict = params.model_dump()

        if self.settings.mock_mode:
            logger.info("watsonx mock mode: simulating update_shot_status for %s", params.shot)
            result = {
                "success": True,
                "project": params.project,
                "sequence": params.sequence,
                "shot": params.shot,
                "shot_id": f"shot-{params.project}_{params.sequence}_{params.shot}",
                "previous_status": "ip",
                "new_status": params.new_status,
                "updated_by": params.updated_by or "watsonx_orchestrate",
                "updated_at": now_utc_iso(),
            }
            self._record_audit("update_shot_status", param_dict, "SUCCESS", result=result)
            return result

        try:
            resp = self.client.run_workflow("update_shot_status_skill", param_dict)
            output = resp.get("outputs", {})
            result = {
                "success": True,
                "project": params.project,
                "sequence": params.sequence,
                "shot": params.shot,
                "shot_id": output.get("shot_id", f"shot-{params.project}_{params.sequence}_{params.shot}"),
                "previous_status": output.get("previous_status", "ip"),
                "new_status": params.new_status,
                "updated_by": params.updated_by or "watsonx_orchestrate",
                "updated_at": now_utc_iso(),
            }
            self._record_audit("update_shot_status", param_dict, "SUCCESS", result=result)
            return result
        except WatsonxError as exc:
            self._record_audit("update_shot_status", param_dict, "FAILED", error=str(exc))
            raise

    # ─────────────────────────────────────────────────────────────
    # 4. create_incident
    # ─────────────────────────────────────────────────────────────
    def create_incident(self, params: CreateIncidentParams) -> dict[str, Any]:
        """Create incident ticket in studio tracking system via watsonx."""
        param_dict = params.model_dump()

        if self.settings.mock_mode:
            logger.info("watsonx mock mode: simulating create_incident '%s'", params.title)
            ticket_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
            result = {
                "success": True,
                "ticket_id": ticket_id,
                "title": params.title,
                "severity": params.severity,
                "category": params.category,
                "related_incident_id": params.related_incident_id,
                "assignee": params.assignee or "unassigned",
                "status": "OPEN",
                "created_at": now_utc_iso(),
            }
            self._record_audit("create_incident", param_dict, "SUCCESS", result=result)
            return result

        try:
            resp = self.client.run_workflow("create_incident_skill", param_dict)
            output = resp.get("outputs", {})
            result = {
                "success": True,
                "ticket_id": output.get("ticket_id", f"INC-{uuid.uuid4().hex[:6].upper()}"),
                "title": params.title,
                "severity": params.severity,
                "category": params.category,
                "related_incident_id": params.related_incident_id,
                "assignee": params.assignee or "unassigned",
                "status": "OPEN",
                "created_at": now_utc_iso(),
            }
            self._record_audit("create_incident", param_dict, "SUCCESS", result=result)
            return result
        except WatsonxError as exc:
            self._record_audit("create_incident", param_dict, "FAILED", error=str(exc))
            raise

    # ─────────────────────────────────────────────────────────────
    # 5. notify_team
    # ─────────────────────────────────────────────────────────────
    def notify_team(self, params: NotifyTeamParams) -> dict[str, Any]:
        """Dispatch team notifications via watsonx."""
        param_dict = params.model_dump()

        if self.settings.mock_mode:
            logger.info("watsonx mock mode: simulating notify_team on '%s'", params.channel)
            result = {
                "success": True,
                "message_id": f"msg-{uuid.uuid4().hex[:8]}",
                "channel": params.channel,
                "urgency": params.urgency,
                "delivered_at": now_utc_iso(),
                "mentions_count": len(params.mentions or []),
                "status": "DELIVERED",
            }
            self._record_audit("notify_team", param_dict, "SUCCESS", result=result)
            return result

        try:
            resp = self.client.run_workflow("notify_team_skill", param_dict)
            output = resp.get("outputs", {})
            result = {
                "success": True,
                "message_id": output.get("message_id", f"msg-{uuid.uuid4().hex[:8]}"),
                "channel": params.channel,
                "urgency": params.urgency,
                "delivered_at": now_utc_iso(),
                "mentions_count": len(params.mentions or []),
                "status": "DELIVERED",
            }
            self._record_audit("notify_team", param_dict, "SUCCESS", result=result)
            return result
        except WatsonxError as exc:
            self._record_audit("notify_team", param_dict, "FAILED", error=str(exc))
            raise

    # ─────────────────────────────────────────────────────────────
    # 6. generate_postmortem
    # ─────────────────────────────────────────────────────────────
    def generate_postmortem(self, params: GeneratePostmortemParams) -> dict[str, Any]:
        """Generate studio postmortem report via watsonx."""
        param_dict = params.model_dump()

        if self.settings.mock_mode:
            logger.info("watsonx mock mode: simulating postmortem for %s", params.incident_id)
            report_id = f"PM-{params.incident_id}-{uuid.uuid4().hex[:4].upper()}"
            result = {
                "success": True,
                "report_id": report_id,
                "incident_id": params.incident_id,
                "title": params.title,
                "root_cause": params.root_cause,
                "format": "markdown",
                "report_url": f"https://studio.internal/reports/{report_id}",
                "generated_at": now_utc_iso(),
                "status": "PUBLISHED",
            }
            self._record_audit("generate_postmortem", param_dict, "SUCCESS", result=result)
            return result

        try:
            resp = self.client.run_workflow("generate_postmortem_skill", param_dict)
            output = resp.get("outputs", {})
            result = {
                "success": True,
                "report_id": output.get("report_id", f"PM-{params.incident_id}-{uuid.uuid4().hex[:4].upper()}"),
                "incident_id": params.incident_id,
                "title": params.title,
                "root_cause": params.root_cause,
                "format": "markdown",
                "report_url": output.get("report_url", f"https://studio.internal/reports/{params.incident_id}"),
                "generated_at": now_utc_iso(),
                "status": "PUBLISHED",
            }
            self._record_audit("generate_postmortem", param_dict, "SUCCESS", result=result)
            return result
        except WatsonxError as exc:
            self._record_audit("generate_postmortem", param_dict, "FAILED", error=str(exc))
            raise

    # ─────────────────────────────────────────────────────────────
    # 7. get_job_status
    # ─────────────────────────────────────────────────────────────
    def get_job_status(self, params: GetJobStatusParams) -> dict[str, Any]:
        """Inspect status of farm job."""
        param_dict = params.model_dump()
        if self.settings.mock_mode:
            result = {
                "success": True,
                "job_id": params.job_id,
                "status": "FAILED",
                "error_code": "CUDA_OUT_OF_MEMORY",
                "frame_count": 250,
                "completed_frames": 112,
                "failed_frames": [113, 114],
                "last_active_node": "node-blade-42",
                "queried_at": now_utc_iso(),
            }
            self._record_audit("get_job_status", param_dict, "SUCCESS", result=result)
            return result

        try:
            resp = self.client.run_workflow("get_job_status_skill", param_dict)
            output = resp.get("outputs", {})
            result = {
                "success": True,
                "job_id": params.job_id,
                "status": output.get("status", "UNKNOWN"),
                "queried_at": now_utc_iso(),
            }
            self._record_audit("get_job_status", param_dict, "SUCCESS", result=result)
            return result
        except WatsonxError as exc:
            self._record_audit("get_job_status", param_dict, "FAILED", error=str(exc))
            raise

    # ─────────────────────────────────────────────────────────────
    # 8. get_node_health
    # ─────────────────────────────────────────────────────────────
    def get_node_health(self, params: GetNodeHealthParams) -> dict[str, Any]:
        """Query render node metrics."""
        param_dict = params.model_dump()
        if self.settings.mock_mode:
            result = {
                "success": True,
                "node_id": params.node_id,
                "status": "DEGRADED",
                "gpu_memory_used_percent": 99.4,
                "gpu_temperature_celsius": 84.5,
                "cpu_utilization_percent": 88.0,
                "quarantined": False,
                "queried_at": now_utc_iso(),
            }
            self._record_audit("get_node_health", param_dict, "SUCCESS", result=result)
            return result

        try:
            resp = self.client.run_workflow("get_node_health_skill", param_dict)
            output = resp.get("outputs", {})
            result = {
                "success": True,
                "node_id": params.node_id,
                "status": output.get("status", "HEALTHY"),
                "queried_at": now_utc_iso(),
            }
            self._record_audit("get_node_health", param_dict, "SUCCESS", result=result)
            return result
        except WatsonxError as exc:
            self._record_audit("get_node_health", param_dict, "FAILED", error=str(exc))
            raise


# Default singleton instance
watsonx_adapter = WatsonxWorkflowAdapter()
