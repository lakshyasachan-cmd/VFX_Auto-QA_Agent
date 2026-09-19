"""
FastAPI REST router for the MCP Integration subsystem.
Exposes:
- GET  /api/v1/mcp/tools      (List all available workflow tools and parameters)
- GET  /api/v1/mcp/tools/{id} (Get metadata and parameter schema for a specific tool)
- POST /api/v1/mcp/execute    (Execute an action tool under security gateway verification)
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.mcp.schemas import (
    MCPToolCallRequest,
    MCPToolCallResponse,
    ToolDefinition,
)
from backend.mcp.server import MCPServer, mcp_server

from backend.common.auth import AuthenticatedUser, authenticate_request
from backend.common.logging import (
    approval_id_ctx,
    incident_id_ctx,
    mcp_execution_id_ctx,
    get_logger,
)

logger = get_logger("vfx.mcp.api")

router = APIRouter(prefix="/api/v1/mcp", tags=["MCP Tools"])


def get_mcp_server(request: Request) -> MCPServer:
    if hasattr(request.app.state, "mcp_server"):
        return request.app.state.mcp_server
    return mcp_server


@router.get("/tools", response_model=list[ToolDefinition], summary="List available MCP workflow tools")
async def list_tools_endpoint(
    request: Request = None,  # type: ignore
    user: Optional[AuthenticatedUser] = None,
):
    server = get_mcp_server(request)
    return server.list_tools()


@router.get("/tools/{tool_name}", response_model=ToolDefinition, summary="Get details and schema for an MCP tool")
async def get_tool_endpoint(
    tool_name: str,
    request: Request = None,  # type: ignore
    user: Optional[AuthenticatedUser] = None,
):
    server = get_mcp_server(request)
    tool = server.get_tool_info(tool_name)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP tool '{tool_name}' is not registered on this server.",
        )
    return tool


@router.post("/execute", response_model=MCPToolCallResponse, summary="Execute an MCP tool under governance checks")
async def execute_tool_endpoint(
    payload: MCPToolCallRequest,
    request: Request = None,  # type: ignore
    user: AuthenticatedUser = Depends(authenticate_request),
):
    # Set execution trace context
    if payload.context:
        if payload.context.incident_id:
            incident_id_ctx.set(payload.context.incident_id)
        if payload.context.approval_id:
            approval_id_ctx.set(payload.context.approval_id)

    server = get_mcp_server(request)
    result = server.execute_request(payload)
    if result.execution_id:
        mcp_execution_id_ctx.set(result.execution_id)

    if not result.success:
        # Determine appropriate status code based on rejection/block reason
        err_msg = result.error or "Tool execution rejected"
        if "Missing mandatory MCPExecutionContext" in err_msg or "Unauthorized" in err_msg:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=err_msg)
        if "Execution blocked" in err_msg or "Action identity mismatch" in err_msg or "Duplicate execution" in err_msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err_msg)
        if "Parameter validation failed" in err_msg:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=err_msg)
        if "Tool" in err_msg and "not found" in err_msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=err_msg)

    return result
