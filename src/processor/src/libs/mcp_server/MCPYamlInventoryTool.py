# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Kubernetes YAML Inventory MCP Tool.

This MCP tool generates a deterministic inventory for converted Kubernetes YAML manifests.
It is intended to remove guesswork from operator-grade runbooks by extracting:
- apiVersion/kind
- metadata.name/metadata.namespace
- a suggested apply order (grouped)

The tool reads YAML blobs from Azure Blob Storage and writes a structured inventory
artifact back to Blob Storage (typically into the process output folder).

Example:
    from libs.mcp_server.MCPYamlInventoryTool import get_yaml_inventory_mcp

    yaml_inv_tool = get_yaml_inventory_mcp()
"""

import os
from pathlib import Path

from agent_framework import MCPStdioTool


def get_yaml_inventory_mcp() -> MCPStdioTool:
    """Create and return the YAML inventory MCP tool instance."""

    return MCPStdioTool(
        name="yaml_inventory_service",
        description="MCP tool to generate a converted YAML inventory JSON for runbooks",
        command="uv",
        args=[
            f"--directory={str(Path(os.path.dirname(__file__)).joinpath('yaml_inventory'))}",
            "run",
            "mcp_yaml_inventory.py",
        ],
        env=dict(os.environ),
    )
