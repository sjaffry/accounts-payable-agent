"""
Factory for the Xero MCP toolset.

Creates an MCPToolset that connects to the official Xero MCP server
(@xeroapi/xero-mcp-server) via stdio, reusing the existing OAuth tokens
managed by xero_auth.py.

The bearer token is passed via the XERO_CLIENT_BEARER_TOKEN environment
variable, which takes precedence over client ID/secret in the MCP server.

Usage:
    from accounts_payable.shared_libraries.xero_mcp_toolset import create_xero_mcp_toolset

    toolset = create_xero_mcp_toolset()
    agent = LlmAgent(tools=[toolset, ...])
"""

from __future__ import annotations

import os

from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters

from .xero_auth import get_access_token


def create_xero_mcp_toolset() -> MCPToolset:
    """Create an MCPToolset connected to the Xero MCP server.

    Passes the current Xero access token via XERO_CLIENT_BEARER_TOKEN so the
    MCP server authenticates without a separate OAuth flow.

    Returns:
        MCPToolset configured to run @xeroapi/xero-mcp-server via npx.
    """
    env = {
        **os.environ,
        "XERO_CLIENT_BEARER_TOKEN": get_access_token(),
        "XERO_TENANT_ID": os.environ.get("XERO_TENANT_ID", ""),
    }

    return MCPToolset(
        connection_params=StdioServerParameters(
            command="npx",
            args=["-y", "@xeroapi/xero-mcp-server"],
            env=env,
        )
    )
