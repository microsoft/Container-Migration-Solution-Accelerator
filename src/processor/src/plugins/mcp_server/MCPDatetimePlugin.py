import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def get_datetime_plugin():
    """
    Create an MCP plugin for datetime operations.
    Cross-platform compatible for Windows, Linux, and macOS.

    Returns:
        MCPStdioPlugin: Configured datetime MCP plugin, or None if MCP not available

    Raises:
        RuntimeError: If MCP setup validation fails
    """
    try:
        # Lazy import to avoid hanging during module import
        from semantic_kernel.connectors.mcp import MCPStdioPlugin

        return MCPStdioPlugin(
            name="datetime_service",
            description="MCP plugin for datetime operations",
            command="uv",
            args=[
                f"--directory={str(Path(os.path.dirname(__file__)).joinpath('mcp_datetime'))}",
                "run",
                "mcp_datetime.py",
            ]
        )

    except ImportError as e:
        logger.warning(f"MCP support not available for datetime plugin: {e}")
        logger.info("Install the 'mcp' package to enable MCP plugin support")
        return None
    except Exception as e:
        logger.error(f"Failed to create datetime MCP plugin: {e}")
        return None


def is_mcp_available() -> bool:
    """Check if MCP support is available."""
    try:
        from semantic_kernel.connectors.mcp import MCPStdioPlugin
        return True
    except ImportError:
        return False
