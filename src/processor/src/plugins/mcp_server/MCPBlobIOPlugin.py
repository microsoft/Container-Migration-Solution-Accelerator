import os
from pathlib import Path


def get_blob_file_operation_plugin():
    """
    Create an MCP plugin for Blob File Operations.
    Cross-platform compatible for Windows, Linux, and macOS.

    Returns:
        MCPStdioPlugin: Configured Blob File Operations MCP plugin

    Raises:
        RuntimeError: If MCP setup validation fails
    """
    # Lazy import to avoid hanging during module import
    from semantic_kernel.connectors.mcp import MCPStdioPlugin

    return MCPStdioPlugin(
        name="azure_blob_io_service",
        description="MCP plugin for Azure Blob Storage Operations",
        command="uv",
        args=[
            f"--directory={str(Path(os.path.dirname(__file__)).joinpath('mcp_blob_io_operation'))}",
            "run",
            "mcp_blob_io_operation.py",
        ],
        env=dict(
            os.environ
        ),  # passing all env vars so the separated MCP instance has access to same environment values, particularly for Azure
    )
