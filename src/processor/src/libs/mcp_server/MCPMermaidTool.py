"""Mermaid validation/fix MCP Tool.

This module provides Mermaid diagram validation and best-effort auto-fixing through MCP.
It runs a local FastMCP server over stdio via `uv` (same pattern as other tools in
`libs.mcp_server`).

Usage (agent-framework style):

    from libs.mcp_server.MCPMermaidTool import get_mermaid_mcp
    from libs.agent_framework.mcp_context import MCPContext

    mermaid_tool = get_mermaid_mcp()
    async with MCPContext(tools=[mermaid_tool]) as mcp_ctx:
        ...

"""

from __future__ import annotations

import os
from pathlib import Path

from agent_framework import MCPStdioTool


def get_mermaid_mcp() -> MCPStdioTool:
    """Create and return a Mermaid validation/fix MCP tool instance."""

    mermaid_dir = Path(os.path.dirname(__file__)).joinpath("mermaid")

    return MCPStdioTool(
        name="mermaid_service",
        description="MCP tool for Mermaid diagram validation and best-effort auto-fix",
        command="uv",
        args=[
            f"--directory={str(mermaid_dir)}",
            "run",
            "mcp_mermaid.py",
        ],
        env=dict(os.environ),
    )
