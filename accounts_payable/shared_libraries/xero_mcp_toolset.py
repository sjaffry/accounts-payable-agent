"""
Factory for the Xero MCP toolset.

Connects to the Xero MCP server running as a standalone HTTP SSE service
(xero-mcp-server/server.mjs). The server handles Xero authentication
internally using XERO_CLIENT_ID / XERO_CLIENT_SECRET and spawns a fresh
@xeroapi/xero-mcp-server subprocess per SSE connection.

Required environment variables:
    XERO_MCP_SERVER_URL  URL of the running xero-mcp-server SSE endpoint.
                         Default: http://localhost:3000/sse
    MCP_API_KEY          Static API key for the xero-mcp-server.
                         Omit when running locally without auth.

Usage:
    from accounts_payable.shared_libraries.xero_mcp_toolset import create_xero_mcp_toolset

    toolset = create_xero_mcp_toolset()
    agent = LlmAgent(tools=[toolset, ...])
"""

from __future__ import annotations

import os

from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, SseConnectionParams


def create_xero_mcp_toolset() -> MCPToolset:
    """Create an MCPToolset that connects to the Xero MCP HTTP SSE server.

    Returns:
        MCPToolset configured to connect via the XERO_MCP_SERVER_URL endpoint.
    """
    url = os.environ.get("XERO_MCP_SERVER_URL", "http://localhost:3000/sse")
    api_key = os.environ.get("MCP_API_KEY", "")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    return MCPToolset(connection_params=SseConnectionParams(url=url, headers=headers))

