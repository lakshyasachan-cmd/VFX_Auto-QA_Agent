"""
Pydantic schemas and parameters for the MCP (Model Context Protocol) Integration subsystem.
Defines parameter validation schemas for all 8 controlled VFX workflow tools,
execution contexts, and tool call responses.
"""

from enum import Enum
from typing import Any, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ToolName(str, Enum):
    GET_JOB_STATUS = "get_job_status"
    GET_NODE_HEALTH = "get_node_health"
    RETRY_RENDER_JOB = "retry_render_job"
    ASSIGN_PIPELINE_TD = "assign_pipeline_td"
    UPDATE_SHOT_STATUS = "update_shot_status"
    CREATE_INCIDENT = "create_incident"
    NOTIFY_TEAM = "notify_team"
    GENERATE_POSTMORTEM = "generate_postmortem"


# ─────────────────────────────────────────────────────────────
# 1. Parameter Schemas for Controlled Tools
# ─────────────────────────────────────────────────────────────

class GetJobStatusParams(BaseModel):
    """Parameters for get_job_status tool."""
    model_config = ConfigDict(extra="forbid")
    job_id: str = Field(..., min_length=1, description="Unique render farm job ID (e.g. job-1042)")


class GetNodeHealthParams(BaseModel):
    """Parameters for get_node_health tool."""
    model_config = ConfigDict(extra="forbid")
    node_id: str = Field(..., min_length=1, description="Identifier of the render node (e.g. node-blade-42)")


class RetryRenderJobParams(BaseModel):
    """Parameters for retry_render_job tool."""
    model_config = ConfigDict(extra="forbid")
    job_id: str = Field(..., min_length=1, description="Job identifier to retry")
    node_class: Optional[str] = Field("standard", description="Node class or pool (e.g. gpu-80gb, standard, high-mem)")
    priority_boost: Optional[int] = Field(0, ge=0, le=100, description="Priority increase (0-100)")
    frame_range: Optional[str] = Field(None, description="Optional frame range to retry (e.g. '1001-1050')")
    excluded_nodes: Optional[list[str]] = Field(default_factory=list, description="List of node IDs to avoid")


class AssignPipelineTDParams(BaseModel):
    """Parameters for assign_pipeline_td tool."""
    model_config = ConfigDict(extra="forbid")
    incident_id: str = Field(..., min_length=1, description="Incident identifier")
    td_name: str = Field(..., min_length=1, description="Name or handle of assigned Pipeline TD")
    priority: str = Field("medium", description="critical, high, medium, low")
    department: str = Field("pipeline", description="Department: lighting, compositing, fx, modeling, rigging, pipeline")
    notes: Optional[str] = Field("", description="Assignment instructions or notes")


class UpdateShotStatusParams(BaseModel):
    """Parameters for update_shot_status tool."""
    model_config = ConfigDict(extra="forbid")
    project: str = Field(..., min_length=1, description="Project code (e.g. 'TEST_PROJECT')")
    sequence: str = Field(..., min_length=1, description="Sequence code (e.g. 'seq_01')")
    shot: str = Field(..., min_length=1, description="Shot code (e.g. 'sh_0010')")
    new_status: str = Field(..., min_length=1, description="New status (e.g. 'ip', 'review', 'on_hold', 'wtg', 'approved')")
    notes: Optional[str] = Field("", description="Status change justification")
    updated_by: Optional[str] = Field(None, description="User or agent initiating the change")


class CreateIncidentParams(BaseModel):
    """Parameters for create_incident tool."""
    model_config = ConfigDict(extra="forbid")
    title: str = Field(..., min_length=1, description="Incident summary title")
    description: str = Field(..., min_length=1, description="Detailed incident description")
    severity: str = Field("medium", description="critical, high, medium, low, info")
    category: str = Field("render", description="render, hardware, asset, pipeline, storage")
    related_incident_id: Optional[str] = Field(None, description="Related incident or correlation ID")
    assignee: Optional[str] = Field(None, description="Initial assignee user handle")
    labels: Optional[list[str]] = Field(default_factory=list, description="Tags or labels")


class NotifyTeamParams(BaseModel):
    """Parameters for notify_team tool."""
    model_config = ConfigDict(extra="forbid")
    channel: str = Field(..., min_length=1, description="Notification channel (e.g. '#pipeline-alerts')")
    message: str = Field(..., min_length=1, description="Message body")
    urgency: str = Field("normal", description="immediate, high, normal, low")
    mentions: Optional[list[str]] = Field(default_factory=list, description="List of user handles to mention")
    thread_id: Optional[str] = Field(None, description="Existing thread ID for replies")


class GeneratePostmortemParams(BaseModel):
    """Parameters for generate_postmortem tool."""
    model_config = ConfigDict(extra="forbid")
    incident_id: str = Field(..., min_length=1, description="Incident ID to summarize")
    title: str = Field(..., min_length=1, description="Report title")
    root_cause: str = Field(..., min_length=1, description="Determined root cause")
    summary: str = Field(..., min_length=1, description="Executive summary")
    timeline: Optional[list[dict[str, Any]]] = Field(default_factory=list, description="Key events timeline")
    preventive_measures: Optional[list[str]] = Field(default_factory=list, description="Action items to prevent recurrence")


# ─────────────────────────────────────────────────────────────
# 2. Security Execution Context & Protocol Schemas
# ─────────────────────────────────────────────────────────────

class MCPExecutionContext(BaseModel):
    """
    Mandatory execution context required for any MCP tool invocation.
    Guarantees that untrusted LLMs cannot trigger executions without policy approval.
    """
    model_config = ConfigDict(extra="ignore")

    approval_id: str = Field(..., min_length=1, description="ID of the approved governance request")
    actor: str = Field(..., min_length=1, description="Authorized user or service identity calling the tool")
    incident_id: Optional[str] = Field(default=None, description="Associated incident ID")
    plan_id: Optional[str] = Field(default=None, description="Associated remediation plan ID")
    auth_token: Optional[str] = Field(default=None, description="Security bearer or service token")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context metadata")


class MCPToolCallRequest(BaseModel):
    """Request envelope for invoking an MCP tool."""
    model_config = ConfigDict(extra="ignore")

    tool_name: str = Field(..., description="Tool name to execute")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    context: MCPExecutionContext = Field(..., description="Mandatory security context with verified approval")


class MCPToolCallResponse(BaseModel):
    """Standardized response from MCP tool execution."""
    model_config = ConfigDict(extra="ignore")

    success: bool
    tool_name: str
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    audit_id: Optional[str] = None
    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class ToolDefinition(BaseModel):
    """Metadata and parameter schema for an exposed MCP tool."""
    name: str
    description: str
    parameters_schema: dict[str, Any]
    requires_approval: bool = True
