"""
Shared Tool Tracking Utilities for Migration Steps

This module provides reusable tool tracking functionality that can be used
across all migration steps to track agent tool usage consistently.
"""

import logging

logger = logging.getLogger(__name__)


class ToolTrackingMixin:
    """Mixin class to add tool tracking capabilities to migration steps."""

    async def detect_and_track_tool_usage(
        self, process_id: str, agent_name: str, content: str
    ) -> None:
        """
        Detect and track tool usage in agent messages.

        This method analyzes agent message content to identify when tools are being used
        and tracks the usage in telemetry for monitoring and debugging purposes.
        """
        if not hasattr(self, "telemetry") or not self.telemetry:
            return

        try:
            # Common tool usage patterns in agent messages
            tool_patterns = {
                # MCP Blob operations
                "blob": [
                    "list_blobs_in_container",
                    "read_blob_content",
                    "save_content_to_blob",
                    "list_containers",
                    "find_blobs",
                    "check_blob_exists",
                    "delete_blob",
                    "copy_blob",
                    "move_blob",
                ],
                # MCP File operations
                "file": [
                    "list_files_in_directory",
                    "open_file_content",
                    "save_content_to_file",
                    "find_files",
                    "check_file_exists",
                    "analyze_file_quality",
                    "copy_file",
                    "move_file",
                    "delete_file",
                    "rename_file",
                ],
                # MCP Microsoft Docs
                "msdocs": [
                    "microsoft_docs_search",
                    "microsoft_docs_fetch",
                ],
                # MCP Datetime
                "datetime": [
                    "get_current_time",
                    "format_datetime",
                    "get_timestamp",
                ],
                # MCP Context7 (library documentation)
                "context7": [
                    "resolve_library_id",
                    "get_library_docs",
                ],
                # MCP Memory operations
                "memory": [
                    "create_entities",
                    "add_observations",
                    "search_nodes",
                    "read_graph",
                    "create_relations",
                ],
                # Function Apps operations
                "functionapp": [
                    "deploy_function",
                    "list_functions",
                    "invoke_function",
                ],
                # Azure Bicep operations
                "bicep": [
                    "get_azure_verified_module",
                    "get_az_resource_type_schema",
                    "list_az_resource_types",
                    "get_bicep_best_practices",
                ],
            }

            # Detect tool usage in content
            content_lower = content.lower()
            for tool_category, actions in tool_patterns.items():
                for action in actions:
                    if action.lower() in content_lower:
                        # Extract context around the tool usage
                        tool_context = self._extract_tool_context(content, action)

                        # Track the tool usage
                        await self.telemetry.track_tool_usage(
                            process_id=process_id,
                            agent_name=agent_name,
                            tool_name=tool_category,
                            tool_action=action,
                            tool_details=tool_context,
                            tool_result_preview="",  # We can't see results in this callback
                        )

                        logger.info(
                            f"[TOOL_DETECTED] {agent_name} used {tool_category}.{action}"
                        )
                        break  # Only track first detected tool per message

            # Also detect general function call patterns
            function_indicators = [
                "function_call",
                "calling function",
                "invoke tool",
                "using tool",
                "executing function",
                "tool invocation",
            ]

            for indicator in function_indicators:
                if indicator in content_lower:
                    await self.telemetry.track_tool_usage(
                        process_id=process_id,
                        agent_name=agent_name,
                        tool_name="unknown",
                        tool_action="function_call",
                        tool_details=f"Generic function call detected: {indicator}",
                        tool_result_preview="",
                    )
                    break  # Only track one generic pattern per message

        except Exception as e:
            logger.warning(f"Error detecting tool usage: {e}")
            # Don't let tool detection errors break the main flow

    def _extract_tool_context(self, content: str, tool_action: str) -> str:
        """Extract context around tool usage for better tracking."""
        try:
            # Find the line containing the tool action
            lines = content.split("\n")
            for line in lines:
                if tool_action.lower() in line.lower():
                    # Return the line with some context, trimmed to reasonable length
                    context = line.strip()
                    if len(context) > 150:
                        context = context[:150] + "..."
                    return context
            return f"Tool action: {tool_action}"
        except Exception:
            return f"Tool action: {tool_action}"

    async def create_enhanced_agent_callback(
        self, process_id: str, step_name: str, callback_name: str = "response"
    ):
        """
        Create an enhanced agent response callback with tool tracking.

        Args:
            process_id: The process ID for telemetry
            step_name: Name of the step (for logging context)
            callback_name: Type of callback (response, completion, etc.)

        Returns:
            Async callback function for agent responses
        """

        async def enhanced_agent_response_callback(message):
            try:
                # Extract agent info from message
                agent_name = getattr(message, "name", "Unknown_Agent")
                content = getattr(message, "content", "No content")

                print(f"📝 [{step_name.upper()}_CALLBACK] Agent: {agent_name}")
                print(f"📝 [{step_name.upper()}_CALLBACK] Content: {content[:200]}...")

                # Enhanced tool usage detection and tracking
                await self.detect_and_track_tool_usage(process_id, agent_name, content)

                # Standard telemetry update
                if hasattr(self, "telemetry") and self.telemetry:
                    await self.telemetry.update_agent_activity(
                        process_id,
                        agent_name,
                        f"{step_name}_{callback_name}",
                        f"{step_name.title()} phase response: {content[:200]}...",
                    )

            except Exception as e:
                print(f"⚠️ [{step_name.upper()}_CALLBACK ERROR] {e}")
                logger.warning(f"Agent callback error in {step_name}: {e}")
                # Continue execution even if callback fails

        return enhanced_agent_response_callback
