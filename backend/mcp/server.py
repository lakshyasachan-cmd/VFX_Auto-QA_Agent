"""
MCP Server class encapsulating the MCP Tool Protocol.
Provides tool enumeration, capabilities discovery, and execution dispatch through the security gateway.
"""

from typing import Any, Callable, Optional

from backend.governance.service import GovernanceService, governance_service
from backend.mcp.gateway import MCPExecutionGateway
from backend.mcp.schemas import (
    MCPExecutionContext,
    MCPToolCallRequest,
    MCPToolCallResponse,
    ToolDefinition,
)
from backend.mcp.tools import TOOL_REGISTRY


class MCPServer:
    """
    Model Context Protocol (MCP) Server for controlled VFX workflows.
    Exposes discovery of tools and delegates execution exclusively via MCPExecutionGateway.
    """

    def __init__(
        self,
        name: str = "vfx-pipeline-orchestrate-mcp",
        version: str = "1.0.0",
        governance_svc: Optional[GovernanceService] = None,
        custom_tool_registry: Optional[dict[str, tuple[type, Callable[[Any], dict[str, Any]]]]] = None,
    ) -> None:
        self.name = name
        self.version = version
        self.governance_svc = governance_svc or governance_service
        self.gateway = MCPExecutionGateway(
            governance_svc=self.governance_svc,
            custom_tool_registry=custom_tool_registry or TOOL_REGISTRY,
        )

    def list_tools(self) -> list[ToolDefinition]:
        """List all exposed VFX workflow tools with JSON schemas."""
        return self.gateway.get_registered_tools()

    def get_tool_info(self, tool_name: str) -> Optional[ToolDefinition]:
        """Get schema and metadata for a single tool."""
        for tool in self.list_tools():
            if tool.name == tool_name:
                return tool
        return None

    def call_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        context: Optional[MCPExecutionContext] = None,
    ) -> MCPToolCallResponse:
        """
        Execute an MCP tool via the security gateway.
        Enforces policy approval, action identity, authorization, and audit trail.
        """
        return self.gateway.execute_tool(
            tool_name=tool_name,
            parameters=parameters,
            context=context,
        )

    def execute_request(self, request: MCPToolCallRequest) -> MCPToolCallResponse:
        """Handle an incoming MCP tool call envelope."""
        return self.gateway.execute_tool(
            tool_name=request.tool_name,
            parameters=request.parameters,
            context=request.context,
        )


# Global default instance
mcp_server = MCPServer()
