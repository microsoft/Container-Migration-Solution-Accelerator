try:
    from semantic_kernel.connectors.mcp import MCPStreamableHttpPlugin

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    MCPStreamableHttpPlugin = None


def get_microsoft_docs_plugin():
    """
    Create an MCP Streamable HTTP Plugin for Microsoft Learn documentation.

    This plugin provides access to Microsoft's official documentation through
    the Microsoft Learn MCP Server, enabling semantic search and document
    retrieval from Azure, .NET, C#, PowerShell, and other Microsoft technologies.

    Available tools:
    - microsoft_docs_search: Semantic search against Microsoft documentation
    - microsoft_docs_fetch: Fetch complete documentation pages in markdown format

    Returns:
        MCPStreamableHttpPlugin: Configured plugin for Microsoft Learn MCP Server, or None if MCP not available
    """
    if not MCP_AVAILABLE or MCPStreamableHttpPlugin is None:
        return None

    return MCPStreamableHttpPlugin(
        name="microsoft_docs_service",
        description="Search Microsoft Docs",
        url="https://learn.microsoft.com/api/mcp",
    )
