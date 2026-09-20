"""
Mock tool implementations for the 8 controlled VFX workflow tools:
1. get_job_status
2. get_node_health
3. retry_render_job
4. assign_pipeline_td
5. update_shot_status
6. create_incident
7. notify_team
8. generate_postmortem

Initially ALL tools are mocked.
"""

from datetime import datetime, timezone
from typing import Any, Callable

from backend.mcp.schemas import (
    AssignPipelineTDParams,
    CreateIncidentParams,
    GeneratePostmortemParams,
    GetJobStatusParams,
    GetNodeHealthParams,
    NotifyTeamParams,
    RetryRenderJobParams,
    ToolName,
    UpdateShotStatusParams,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


from backend.integrations.watsonx.adapter import (
    watsonx_adapter,
)


class VFXToolImplementations:
    """
    VFX workflow tools backed by IBM watsonx Orchestrate Integration adapter.
    Dispatches to WatsonxWorkflowAdapter which supports mock mode (WATSONX_MOCK=true)
    and live IBM watsonx Orchestrate skill invocation (WATSONX_MOCK=false).
    """

    @staticmethod
    def get_job_status(params: GetJobStatusParams) -> dict[str, Any]:
        return watsonx_adapter.get_job_status(params)

    @staticmethod
    def get_node_health(params: GetNodeHealthParams) -> dict[str, Any]:
        return watsonx_adapter.get_node_health(params)

    @staticmethod
    def retry_render_job(params: RetryRenderJobParams) -> dict[str, Any]:
        from backend.integrations.render_farm.adapter import farm_adapter
        if farm_adapter.is_live():
            ok = farm_adapter.requeue_job(params.job_id)
            return {
                "success": ok,
                "job_id": params.job_id,
                "source": farm_adapter.farm_type,
                "message": f"Job '{params.job_id}' requeued on {farm_adapter.farm_type} render farm.",
            }
        return watsonx_adapter.retry_render_job(params)

    @staticmethod
    def assign_pipeline_td(params: AssignPipelineTDParams) -> dict[str, Any]:
        return watsonx_adapter.assign_pipeline_td(params)

    @staticmethod
    def update_shot_status(params: UpdateShotStatusParams) -> dict[str, Any]:
        try:
            from backend.integrations.shotgrid.adapter import shotgrid_adapter
            if shotgrid_adapter.is_live():
                ok = shotgrid_adapter.update_shot_status(
                    shot_id_or_code=params.shot_id,
                    new_status=params.status,
                    note=params.note,
                )
                return {
                    "success": ok,
                    "shot_id": params.shot_id,
                    "status": params.status,
                    "source": "shotgrid",
                    "message": f"Shot '{params.shot_id}' status updated to '{params.status}' in ShotGrid.",
                }
        except Exception:
            pass
        return watsonx_adapter.update_shot_status(params)

    @staticmethod
    def create_incident(params: CreateIncidentParams) -> dict[str, Any]:
        return watsonx_adapter.create_incident(params)

    @staticmethod
    def notify_team(params: NotifyTeamParams) -> dict[str, Any]:
        return watsonx_adapter.notify_team(params)

    @staticmethod
    def generate_postmortem(params: GeneratePostmortemParams) -> dict[str, Any]:
        return watsonx_adapter.generate_postmortem(params)


# Mapping of ToolName to parameter model and handler function
TOOL_REGISTRY: dict[str, tuple[type, Callable[[Any], dict[str, Any]]]] = {
    ToolName.GET_JOB_STATUS.value: (GetJobStatusParams, VFXToolImplementations.get_job_status),
    ToolName.GET_NODE_HEALTH.value: (GetNodeHealthParams, VFXToolImplementations.get_node_health),
    ToolName.RETRY_RENDER_JOB.value: (RetryRenderJobParams, VFXToolImplementations.retry_render_job),
    ToolName.ASSIGN_PIPELINE_TD.value: (AssignPipelineTDParams, VFXToolImplementations.assign_pipeline_td),
    ToolName.UPDATE_SHOT_STATUS.value: (UpdateShotStatusParams, VFXToolImplementations.update_shot_status),
    ToolName.CREATE_INCIDENT.value: (CreateIncidentParams, VFXToolImplementations.create_incident),
    ToolName.NOTIFY_TEAM.value: (NotifyTeamParams, VFXToolImplementations.notify_team),
    ToolName.GENERATE_POSTMORTEM.value: (GeneratePostmortemParams, VFXToolImplementations.generate_postmortem),
}
