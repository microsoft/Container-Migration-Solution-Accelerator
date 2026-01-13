"""Azure Blob Storage MCP Tool.

This module provides Azure Blob Storage operations through the Model Context Protocol (MCP).
The tool enables agents to read, write, list, and manage files in Azure Blob Storage,
allowing seamless integration of cloud storage capabilities into AI agent workflows.

The tool runs as a local process using the Stdio transport and automatically inherits
all environment variables (including Azure credentials) for secure authentication.

Key Features:
    - Upload and download blobs
    - List containers and blobs
    - Delete and manage blob storage
    - Cross-platform support (Windows, Linux, macOS)
    - Automatic Azure credential inheritance

Example:
    .. code-block:: python

        from libs.mcp_server.MCPBlobIOTool import get_blob_file_mcp
        from libs.agent_framework.mcp_context import MCPContext
        from agent_framework import ChatAgent

        # Get the Blob Storage MCP tool
        blob_tool = get_blob_file_mcp()

        # Use with MCPContext for TaskGroup-safe management
        async with MCPContext(tools=[blob_tool]) as mcp_ctx:
            async with ChatAgent(client, tools=mcp_ctx.tools) as agent:
                response = await agent.run(
                    "Upload the file 'data.csv' to my Azure storage container 'datasets'"
                )
                print(response)
"""

import os
from pathlib import Path

from agent_framework import MCPStdioTool


def get_blob_file_mcp() -> MCPStdioTool:
    """Create and return an Azure Blob Storage MCP tool instance.

    This function creates an MCPStdioTool that runs a local Python-based Azure Blob Storage
    service using the UV package manager. The tool provides comprehensive blob storage operations
    through the Model Context Protocol, enabling agents to interact with Azure Storage accounts.

    The tool uses the Stdio transport to communicate with a local MCP server process, which
    automatically inherits all environment variables (including AZURE_STORAGE_CONNECTION_STRING,
    AZURE_STORAGE_ACCOUNT_NAME, etc.) for seamless Azure authentication.

    Returns:
        MCPStdioTool: Configured MCP tool for Azure Blob Storage operations.
            The tool provides capabilities including:
            - Upload files to blob containers
            - Download blobs to local filesystem
            - List containers and blobs
            - Delete blobs and containers
            - Get blob properties and metadata
            - Stream large files efficiently
            - Manage access tiers (Hot, Cool, Archive)

    Raises:
        RuntimeError: If the blob_io_operation module is not found or MCP setup fails.
        EnvironmentError: If required Azure credentials are not configured in environment.

    Example:
        Basic blob upload:

        .. code-block:: python

            blob_tool = get_blob_file_mcp()

            async with blob_tool:
                async with ChatAgent(client, tools=[blob_tool]) as agent:
                    result = await agent.run(
                        "Upload 'report.pdf' to container 'documents'"
                    )
                    print(result)

        List and download blobs:

        .. code-block:: python

            from libs.agent_framework.mcp_context import MCPContext

            blob_tool = get_blob_file_mcp()

            async with MCPContext(tools=[blob_tool]) as mcp_ctx:
                async with ChatAgent(client, tools=mcp_ctx.tools) as agent:
                    # List all containers
                    containers = await agent.run("List all my blob containers")
                    print(containers)

                    # Download a specific blob
                    download = await agent.run(
                        "Download 'data.csv' from container 'datasets' to local folder"
                    )
                    print(download)

        Multi-agent workflow with blob operations:

        .. code-block:: python

            blob_tool = get_blob_file_mcp()
            datetime_tool = get_datetime_plugin()

            async with MCPContext(tools=[blob_tool, datetime_tool]) as mcp_ctx:
                # Data processing agent
                async with ChatAgent(client1, tools=mcp_ctx.tools) as processor:
                    data = await processor.run(
                        "Download 'raw_data.csv' from 'input-container'"
                    )

                # Analysis agent
                async with ChatAgent(client2, tools=mcp_ctx.tools) as analyst:
                    result = await analyst.run(
                        f"Analyze the data and upload results to 'output-container'"
                    )

        With custom Azure credentials:

        .. code-block:: python

            import os

            # Set Azure credentials
            os.environ["AZURE_STORAGE_CONNECTION_STRING"] = "your_connection_string"
            # or
            os.environ["AZURE_STORAGE_ACCOUNT_NAME"] = "your_account_name"
            os.environ["AZURE_STORAGE_ACCOUNT_KEY"] = "your_account_key"

            blob_tool = get_blob_file_mcp()

            async with MCPContext(tools=[blob_tool]) as mcp_ctx:
                async with ChatAgent(client, tools=mcp_ctx.tools) as agent:
                    response = await agent.run("Upload 'image.png' to 'media-container'")

    Note:
        **Azure Authentication:**
        The tool requires Azure Storage credentials to be configured via environment variables:

        - ``AZURE_STORAGE_CONNECTION_STRING`` (recommended), or
        - ``AZURE_STORAGE_ACCOUNT_NAME`` + ``AZURE_STORAGE_ACCOUNT_KEY``, or
        - Use DefaultAzureCredential with Managed Identity

        **Environment Variable Inheritance:**
        The tool automatically passes all environment variables to the MCP server process,
        ensuring seamless credential and configuration access.

        **Resource Management:**
        The tool should be used within an async context manager (``async with``) or
        managed by MCPContext to ensure proper process lifecycle management.

        **Cross-Platform Support:**
        The tool works on Windows, Linux, and macOS. The UV package manager handles
        platform-specific differences automatically.

        **Dependencies:**
        Requires the ``blob_io_operation`` module to be available in the
        ``blob_io_operation`` subdirectory with Azure Storage SDK installed.
    """
    return MCPStdioTool(
        name="azure_blob_io_service",
        description="MCP plugin for Azure Blob Storage Operations",
        command="uv",
        args=[
            f"--directory={str(Path(os.path.dirname(__file__)).joinpath('blob_io_operation'))}",
            "run",
            "mcp_blob_io_operation.py",
        ],
        env=dict(
            os.environ
        ),  # passing all env vars so the separated MCP instance has access to same environment values, particularly for Azure
    )
