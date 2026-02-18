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
        env={
            # SECURITY: Pass only the specific env vars needed for Azure Blob
            # operations instead of the full environment. This limits the blast
            # radius if the MCP subprocess is compromised.
            k: v
            for k, v in os.environ.items()
            if k.startswith(("AZURE_", "STORAGE_", "IDENTITY_", "MSI_"))
            or k in ("PATH", "HOME", "USERPROFILE", "TEMP", "TMP", "SystemRoot", "APPDATA")
        },
    )
