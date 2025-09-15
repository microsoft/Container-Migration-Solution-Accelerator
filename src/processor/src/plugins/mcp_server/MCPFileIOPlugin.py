import os
from pathlib import Path


def get_file_io_plugin():
    """
    Create an MCP plugin for file I/O operations.
    Cross-platform compatible for Windows, Linux, and macOS.

    Returns:
        MCPStdioPlugin: Configured file I/O MCP plugin

    Raises:
        RuntimeError: If MCP setup validation fails
    """
    # Lazy import to avoid hanging during module import
    from semantic_kernel.connectors.mcp import MCPStdioPlugin

    return MCPStdioPlugin(
        name="file_operation_service",
        description="MCP plugin for File Operations",
        command="uv",
        args=[
            f"--directory={str(Path(os.path.dirname(__file__)).joinpath('mcp_file_io_operation'))}",
            "run",
            "mcp_file_io_operation.py",
        ]
    )
