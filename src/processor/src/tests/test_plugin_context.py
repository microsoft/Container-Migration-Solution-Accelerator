# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Sanity checks for MCP tool factories.

This file is intentionally runnable as a standalone script (via `uv run python ...`)
*and* importable by test runners.

It validates that our MCP tool factory functions can be imported and constructed
without requiring network access or external credentials.

Why this exists:
- Keeps a quick, smoke-test style entry point for validating the local MCP plugin
  wiring (imports, paths, basic construction).
- Lives under `src/tests/` so all test-related code stays in one place.
"""

from __future__ import annotations

import sys
from pathlib import Path
import unittest


# When executed as a script (`python src/tests/test_plugin_context.py`), Python does
# not automatically include `src/` on the import path. Add it so imports like
# `from libs...` work consistently both in unittest and pytest contexts.
_SRC_DIR = Path(__file__).resolve().parents[1]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


class TestMcpToolFactories(unittest.TestCase):
    """Basic construction tests for MCP tool factories."""

    def test_datetime_tool_constructs(self) -> None:
        from libs.mcp_server.MCPDatetimeTool import get_datetime_mcp

        tool = get_datetime_mcp()
        self.assertIsNotNone(tool)

    def test_mermaid_tool_constructs(self) -> None:
        from libs.mcp_server.MCPMermaidTool import get_mermaid_mcp

        tool = get_mermaid_mcp()
        self.assertIsNotNone(tool)

    def test_blob_io_tool_constructs(self) -> None:
        from libs.mcp_server.MCPBlobIOTool import get_blob_file_mcp

        tool = get_blob_file_mcp()
        self.assertIsNotNone(tool)

    def test_yaml_inventory_tool_constructs(self) -> None:
        from libs.mcp_server.MCPYamlInventoryTool import get_yaml_inventory_mcp

        tool = get_yaml_inventory_mcp()
        self.assertIsNotNone(tool)

    def test_microsoft_docs_tool_constructs(self) -> None:
        from libs.mcp_server.MCPMicrosoftDocs import get_microsoft_docs_mcp

        tool = get_microsoft_docs_mcp()
        self.assertIsNotNone(tool)


if __name__ == "__main__":
    unittest.main()
