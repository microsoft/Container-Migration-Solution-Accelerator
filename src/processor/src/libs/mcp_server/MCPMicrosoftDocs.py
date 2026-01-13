"""Microsoft Learn MCP Tool.

This module provides access to Microsoft Learn documentation through the Model Context Protocol (MCP).
The tool enables agents to search and retrieve documentation from Microsoft Learn, including
Azure, .NET, Microsoft 365, and other Microsoft technologies.

Example:
    .. code-block:: python

        from libs.mcp_server.MCPMicrosoftDocs import get_microsoft_docs_mcp
        from libs.agent_framework.mcp_context import MCPContext
        from agent_framework import ChatAgent

        # Get the Microsoft Docs MCP tool
        docs_tool = get_microsoft_docs_mcp()

        # Use with MCPContext for TaskGroup-safe management
        async with MCPContext(tools=[docs_tool]) as mcp_ctx:
            async with ChatAgent(client, tools=mcp_ctx.tools) as agent:
                response = await agent.run("Search Microsoft Learn for Azure Functions best practices")
                print(response)
"""

from agent_framework import MCPStreamableHTTPTool


def get_microsoft_docs_mcp() -> MCPStreamableHTTPTool:
    """Create and return a Microsoft Learn MCP tool instance.

    This function creates an MCPStreamableHTTPTool that connects to the Microsoft Learn
    MCP server, enabling agents to search and retrieve documentation from Microsoft Learn.
    The tool uses HTTP streaming for efficient communication with the MCP server.

    Returns:
        MCPStreamableHTTPTool: Configured MCP tool for accessing Microsoft Learn documentation.
            The tool provides capabilities to search Microsoft docs, retrieve articles,
            and get technical documentation across all Microsoft technologies.

    Example:
        Basic usage with an agent:

        .. code-block:: python

            docs_tool = get_microsoft_docs_mcp()

            async with docs_tool:
                async with ChatAgent(client, tools=[docs_tool]) as agent:
                    result = await agent.run("Find documentation about Azure App Service")

        Advanced usage with multiple tools:

        .. code-block:: python

            from libs.agent_framework.mcp_context import MCPContext

            docs_tool = get_microsoft_docs_mcp()
            datetime_tool = MCPStdioTool(name="datetime", command="npx", args=["-y", "@modelcontextprotocol/server-datetime"])

            async with MCPContext(tools=[docs_tool, datetime_tool]) as mcp_ctx:
                async with ChatAgent(client, tools=mcp_ctx.tools) as agent:
                    response = await agent.run("What's the latest Azure Functions documentation?")

    Note:
        The returned tool should be used within an async context manager (``async with``)
        or managed by MCPContext to ensure proper connection lifecycle management.

        The Microsoft Learn MCP server endpoint (https://learn.microsoft.com/api/mcp)
        must be accessible from your environment.
    """
    return MCPStreamableHTTPTool(
        name="Microsoft Learn MCP", url="https://learn.microsoft.com/api/mcp"
    )
