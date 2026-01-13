"""Datetime MCP Tool.

This module provides a local datetime service through the Model Context Protocol (MCP).
The tool enables agents to access date and time operations, including getting the current
datetime, formatting dates, calculating time differences, and working with timezones.

The tool runs as a local process using the Stdio transport, providing fast and reliable
datetime operations without external API dependencies.

Example:
    .. code-block:: python

        from libs.mcp_server.MCPDatetimeTool import get_datetime_mcp
        from libs.agent_framework.mcp_context import MCPContext
        from agent_framework import ChatAgent

        # Get the datetime MCP tool
        datetime_tool = get_datetime_mcp()

        # Use with MCPContext for TaskGroup-safe management
        async with MCPContext(tools=[datetime_tool]) as mcp_ctx:
            async with ChatAgent(client, tools=mcp_ctx.tools) as agent:
                response = await agent.run("What time is it right now?")
                print(response)
"""

import os
from pathlib import Path

from agent_framework import MCPStdioTool


def get_datetime_mcp() -> MCPStdioTool:
    """Create and return a datetime MCP tool instance.

    This function creates an MCPStdioTool that runs a local Python-based datetime service
    using the UV package manager. The tool provides datetime operations through the Model
    Context Protocol, enabling agents to query and manipulate date and time information.

    The tool uses the Stdio transport to communicate with a local MCP server process,
    which is automatically started and managed by the tool's lifecycle.

    Returns:
        MCPStdioTool: Configured MCP tool for datetime operations.
            The tool provides capabilities including:
            - Getting current date and time
            - Formatting dates in various formats
            - Calculating time differences
            - Working with timezones
            - Date arithmetic operations

    Example:
        Basic usage with an agent:

        .. code-block:: python

            datetime_tool = get_datetime_mcp()

            async with datetime_tool:
                async with ChatAgent(client, tools=[datetime_tool]) as agent:
                    result = await agent.run("What's today's date?")
                    print(result)

        Advanced usage with multiple tools:

        .. code-block:: python

            from libs.agent_framework.mcp_context import MCPContext

            datetime_tool = get_datetime_mcp()
            weather_tool = get_weather_mcp()

            async with MCPContext(tools=[datetime_tool, weather_tool]) as mcp_ctx:
                async with ChatAgent(client, tools=mcp_ctx.tools) as agent:
                    response = await agent.run(
                        "What's the current time and what's the weather like?"
                    )
                    print(response)

        Using in multi-agent workflows:

        .. code-block:: python

            datetime_tool = get_datetime_mcp()

            async with MCPContext(tools=[datetime_tool]) as mcp_ctx:
                # Share tool across multiple agents
                async with ChatAgent(client1, tools=mcp_ctx.tools) as agent1:
                    time_info = await agent1.run("Get the current time")

                async with ChatAgent(client2, tools=mcp_ctx.tools) as agent2:
                    schedule = await agent2.run(
                        f"Based on the time {time_info}, suggest a meeting slot"
                    )

    Note:
        The returned tool should be used within an async context manager (``async with``)
        or managed by MCPContext to ensure proper process lifecycle management.

        The tool requires UV package manager to be installed and the mcp_datetime
        module to be available in the mcp_datetime subdirectory.

        The MCP server process is automatically started when the tool is entered
        and stopped when the tool is exited, ensuring clean resource management.
    """
    return MCPStdioTool(
        name="datetime_service",
        description="MCP tool for datetime operations",
        command="uv",
        args=[
            f"--directory={str(Path(os.path.dirname(__file__)).joinpath('datetime'))}",
            "run",
            "mcp_datetime.py",
        ],
    )
