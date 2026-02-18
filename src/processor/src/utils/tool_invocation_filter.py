"""
Tool Invocation Security Filter for Semantic Kernel.

Implements an AutoFunctionInvocationFilter that validates tool/function calls
before they are executed. This provides defense-in-depth against:
  - Prompt injection attacks that manipulate the LLM into calling unintended tools
  - Runaway tool invocation chains
  - Invocation of tools not in the approved allow-list

Design Goals:
  - Zero breakage: Only logs a warning (does not block) for unknown plugins,
    so existing functionality is preserved. Switch to blocking mode when ready.
  - Minimal overhead: Simple set-lookup per invocation.
  - Production-safe: Stateless, no external dependencies.

Usage:
    from utils.tool_invocation_filter import ToolInvocationFilter
    kernel.add_filter("auto_function_invocation", ToolInvocationFilter())
"""

from __future__ import annotations

import logging
from typing import Any

from semantic_kernel.filters.auto_function_invocation.auto_function_invocation_context import (
    AutoFunctionInvocationContext,
)
from semantic_kernel.filters.filter_types import FilterTypes

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Approved tool/plugin allow-list
# ---------------------------------------------------------------------------
# Only plugins listed here are expected to be invoked by the LLM.
# Any invocation outside this set is logged as a security warning.
# To hard-block unapproved tools, set BLOCK_UNAPPROVED = True.
APPROVED_PLUGIN_NAMES: set[str] = {
    # MCP plugins
    "azure_blob_io_service",
    "blob",
    "datetime_service",
    "datetime",
    "microsoft_docs_service",
    "msdocs",
    "file_operation_service",
    "file_io",
    # Standard SK prompt plugins
    "ChatPlugin",
    "ClassificationPlugin",
    "QAPlugin",
    "WriterPlugin",
    "SummarizePlugin",
    "CalendarPlugin",
    "ChildrensBookPlugin",
}

# When True, unapproved tool calls are terminated before execution.
# When False (default, safe-rollout mode), they are only logged.
BLOCK_UNAPPROVED: bool = False

# Maximum cumulative auto-invocations tracked per filter instance (safety net).
_MAX_CUMULATIVE_INVOCATIONS: int = 50


class ToolInvocationFilter:
    """
    Semantic Kernel AutoFunctionInvocationFilter that validates every
    auto-invoked tool call against an approved allow-list.

    Register on the kernel with:
        kernel.add_filter(FilterTypes.AUTO_FUNCTION_INVOCATION, ToolInvocationFilter())
    """

    def __init__(self) -> None:
        self._invocation_count: int = 0

    async def __call__(
        self,
        context: AutoFunctionInvocationContext,
        next_handler: Any,
    ) -> None:
        """Intercept every auto-invoked function call."""
        self._invocation_count += 1
        plugin_name: str = context.function.plugin_name or ""
        function_name: str = context.function.name or ""
        fqn = f"{plugin_name}.{function_name}" if plugin_name else function_name

        logger.info(
            f"[SECURITY] Tool invocation #{self._invocation_count}: {fqn}"
        )

        # --- Allow-list check ---
        if plugin_name not in APPROVED_PLUGIN_NAMES:
            msg = (
                f"[SECURITY WARNING] Unapproved plugin invocation detected: "
                f"plugin='{plugin_name}', function='{function_name}'"
            )
            logger.warning(msg)

            if BLOCK_UNAPPROVED:
                logger.warning(
                    f"[SECURITY] BLOCKING unapproved tool call: {fqn}"
                )
                context.terminate = True
                return

        # --- Cumulative invocation safety net ---
        if self._invocation_count > _MAX_CUMULATIVE_INVOCATIONS:
            logger.warning(
                f"[SECURITY] Cumulative invocation limit ({_MAX_CUMULATIVE_INVOCATIONS}) "
                f"exceeded. Terminating auto-invocation chain."
            )
            context.terminate = True
            return

        # Proceed to the actual function execution
        await next_handler(context)
