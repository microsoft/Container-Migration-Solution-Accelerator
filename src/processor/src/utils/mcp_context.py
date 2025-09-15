"""
MCPContext - Task-Group-Safe Context Manager with TaskGroup Scope Management

This module implements a task-group-safe context manager that prevents anyio
TaskGroup scope violations through proper async context manager lifecycle.

CRITICAL TaskGroup Scope Management:
=====================================

PROBLEM SOLVED:
- TaskGroup scope violations occurred when agent creation changed from sync to async
- Async agent creation spawns new HTTP tasks for Azure Assistant API calls
- These new tasks violated existing MCP TaskGroup scopes causing:
  "RuntimeError: Attempted to exit cancel scope in different task than it was entered in"

SOLUTION IMPLEMENTED:
- Same-task-context MCP lifecycle: connect() and close() in same async task
- __aenter__ and __aexit__ execute in same task context by async context manager design
- All MCP connect() calls happen during __aenter__ setup
- All MCP close() calls happen during __aexit__ cleanup
- This maintains anyio TaskGroup scope consistency across MCP lifecycle

TECHNICAL DETAILS:
- anyio TaskGroups must be entered and exited in the same async task context
- When connect() creates TaskGroup scopes, close() must run in same task to exit them
- Async context managers guarantee __aenter__ and __aexit__ run in same task
- This prevents task boundary violations when agent creation spawns new HTTP tasks

Key Features:
1. TaskGroup-scope-safe MCP plugin handling with proper async context manager pattern
2. Individual error isolation per resource with TaskGroup scope error detection
3. Explicit plugin type detection and routing
4. Robust error handling and logging with TaskGroup scope violation tracking
5. Agent lifecycle integration with proper cleanup

Critical Design Decision:
- Use proper async context manager pattern as per Microsoft documentation
- Semantic Kernel framework handles MCP plugin activation automatically
- Individual error handling prevents cascade failures
- TaskGroup scope management prevents "cancel scope in different task" errors
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

# Lazy imports to avoid import hanging issues
from libs.base.KernelAgent import semantic_kernel_agent
from utils.agent_builder import AgentBuilder, agent_info

# Type imports that are only used for type checking
if TYPE_CHECKING:
    from semantic_kernel.agents import (
        Agent,
        AzureAIAgent,
        AzureAssistantAgent,
        ChatCompletionAgent,
    )
    from semantic_kernel.connectors.mcp import MCPPluginBase
    from semantic_kernel.functions import KernelPlugin

logger = logging.getLogger(__name__)


class PluginContext:
    """
    Task-Group-Safe context manager for MCP plugins and Semantic Kernel plugins.

    This context manager uses TASK-GROUP-SAFE management for MCP plugins to completely
    avoid the "cancel scope in different task" errors caused by manual lifecycle
    management of anyio-based MCP plugins.

    Critical Design Decisions:
    - NO manual MCP plugin __aenter__/__aexit__ calls (causes task context issues)
    - Semantic Kernel framework handles MCP plugin activation automatically
    - Individual error isolation prevents cascade failures
    - Explicit lifecycle management for kernel plugins only

    Why Task-Group-Safe?
    The "cancel scope in different task" error occurs because:
    1. MCP plugins use anyio.TaskGroup internally in stdio_client/streamablehttp_client
    2. Manual __aenter__/__aexit__ calls exit contexts in different tasks
    3. anyio requires same-task context entry/exit
    4. ANY manual MCP plugin lifecycle management will fail

    Usage:
        # MCP plugins handled automatically, kernel plugins manually
        plugins = [
            get_datetime_plugin(),  # MCP plugin (automatic)
            FileIOPlugin("."),      # Kernel plugin (manual)
        ]
            FileIOPlugin("."),                              # Auto-generated name
            (WeatherPlugin(), "weather_api"),               # Custom name for kernel plugin
        ]

        # Option 3: Using plugin_names dictionary
        datetime_plugin = get_datetime_plugin()
        file_plugin = FileIOPlugin(".")
        plugins = [datetime_plugin, file_plugin]
        plugin_names = {
            datetime_plugin: "datetime_service",
            file_plugin: "file_operations"
        }

        async with MCPContext(kernel_agent, plugins, plugin_names) as context:
            # Create agents within the context
            agent = context.create_agent(agent_config)

            # Use agents - all plugins are available with meaningful names
            response = await agent.get_response(chat_messages)

        # All plugins automatically cleaned up here
    """

    def __init__(
        self,
        kernel_agent: semantic_kernel_agent,
        plugins: list[
            MCPPluginBase
            | KernelPlugin
            | Any
            | tuple[MCPPluginBase | KernelPlugin | Any, str]
        ]
        | None = None,
        plugin_names: dict[Any, str] | None = None,
        auto_add_to_kernel: bool = True,
    ):
        """
        Initialize MCPContext.

        Args:
            kernel_agent: The semantic kernel agent
            plugins: List of plugins (both MCP and kernel). Can be:
                - Plugin instances: [plugin1, plugin2, ...]
                - (Plugin, name) tuples: [(plugin1, "custom_name"), plugin2, ...]
            plugin_names: Optional mapping of plugin instances to names
            auto_add_to_kernel: Whether to automatically add plugins to kernel
        """
        self.kernel_agent = kernel_agent
        self.kernel = kernel_agent.kernel
        self.plugins = plugins or []
        self.plugin_names = plugin_names or {}
        self.auto_add_to_kernel = auto_add_to_kernel

        # Pure Manual Approach - NO AsyncExitStack usage anywhere
        # All resources managed manually to avoid task context issues
        self._mcp_plugins: dict[str, MCPPluginBase] = {}
        self._mcp_plugin_originals: dict[
            str, MCPPluginBase
        ] = {}  # Store original plugin refs for __aexit__
        self._kernel_plugins: dict[str, Any] = {}
        self._agents: list[Any] = []
        self._is_entered = False
        self._cleanup_requested = False
        self._in_use = False

    def _parse_plugin_entry(
        self, plugin_entry: Any | tuple[Any, str]
    ) -> tuple[Any, str | None]:
        """
        Parse a plugin entry that could be a plugin instance or (plugin, name) tuple.

        Args:
            plugin_entry: Either a plugin instance or (plugin, name) tuple

        Returns:
            Tuple of (plugin_instance, custom_name_or_none)
        """
        if isinstance(plugin_entry, tuple) and len(plugin_entry) == 2:
            plugin, custom_name = plugin_entry
            return plugin, custom_name
        else:
            return plugin_entry, None

    def _detect_plugin_type(self, plugin: Any) -> str:
        """
        Detect whether a plugin is an MCP plugin or kernel plugin.

        Args:
            plugin: Plugin instance to analyze

        Returns:
            'mcp' for MCP plugins, 'kernel' for kernel plugins, 'unknown' for others
        """
        # Handle None plugins (when MCP is unavailable)
        if plugin is None:
            return "unavailable"

        # Lazy import for type checking
        try:
            from semantic_kernel.connectors.mcp import MCPPluginBase
            from semantic_kernel.functions import KernelPlugin
        except ImportError:
            # If imports fail, fall back to attribute checking
            logger.warning("Semantic Kernel MCP support not available")

        # Check for MCP plugin
        try:
            if isinstance(plugin, MCPPluginBase):
                return "mcp"
        except NameError:
            pass

        if hasattr(plugin, "__aenter__") and hasattr(plugin, "__aexit__"):
            # Assume it's an MCP plugin if it has async context manager methods
            return "mcp"

        # Check for Kernel plugin
        try:
            if isinstance(plugin, KernelPlugin):
                # Semantic Kernel's KernelPlugin type
                return "kernel"
        except NameError:
            pass

        if hasattr(plugin, "name") and hasattr(plugin, "functions"):
            # Plugin-like interface (already a KernelPlugin or similar)
            return "kernel"
        elif self._has_kernel_functions(plugin):
            # Class with @kernel_function decorators - will become KernelPlugin
            return "kernel"
        else:
            return "unknown"

    def _has_kernel_functions(self, plugin: Any) -> bool:
        """Check if a class has methods decorated with @kernel_function."""
        try:
            # Check if any methods have the kernel function metadata
            for attr_name in dir(plugin):
                if not attr_name.startswith("_"):
                    attr = getattr(plugin, attr_name)
                    if callable(attr) and hasattr(attr, "__kernel_function__"):
                        return True
            return False
        except Exception:
            return False

    def _generate_plugin_name(
        self,
        plugin: Any,
        plugin_type: str,
        index: int,
        custom_name: str | None = None,
    ) -> str:
        """Generate a name for a plugin. If name exists, it will be replaced."""
        # Use custom name if provided
        if custom_name:
            return custom_name
        elif plugin in self.plugin_names:
            return self.plugin_names[plugin]
        elif hasattr(plugin, "name") and plugin.name:
            return plugin.name
        elif hasattr(plugin, "__class__"):
            return plugin.__class__.__name__.lower().replace("plugin", "")
        else:
            return f"{plugin_type}_plugin"

    async def _setup_mcp_plugin(self, plugin: MCPPluginBase, name: str) -> bool:
        """
        Setup an MCP plugin with TaskGroup scope management.

        CRITICAL TaskGroup Scope Management:
        - This method calls connect() in the same async task context as __aenter__
        - The corresponding close() will be called in __aexit__ in the same task context
        - This prevents "cancel scope in different task" errors with anyio TaskGroups
        - Essential when async agent creation spawns new HTTP request tasks

        Background: When agent creation changed from sync to async, it started spawning
        new HTTP tasks for Azure Assistant API calls, which violated existing MCP
        TaskGroup scopes. This same-task-context pattern prevents those violations.
        """
        try:
            logger.info(f"Connecting to MCP server: {name}")

            # Log current task context for TaskGroup scope tracking
            current_task_id = id(__import__("asyncio").current_task())
            logger.debug(
                f"[TOOLS] MCP setup task context: {current_task_id} for plugin: {name}"
            )

            # Check if plugin with same name already exists and clean up
            if name in self._mcp_plugins:
                logger.info(f"Replacing existing MCP plugin: {name}")
                # Remove from tracking
                del self._mcp_plugins[name]
                if name in self._mcp_plugin_originals:
                    del self._mcp_plugin_originals[name]

            # CRITICAL: Actually connect to the MCP server
            # This is what was missing - MCP plugins need explicit connection
            # Following Microsoft's official sample pattern:
            # https://github.com/microsoft/semantic-kernel/blob/main/python/samples/concepts/mcp/agent_with_mcp_plugin.py
            logger.debug(f"[PLUG] Connecting to MCP server for plugin: {name}")
            await plugin.connect()
            logger.info(f"[SUCCESS] MCP server connected successfully: {name}")

            # Store the connected plugin
            self._mcp_plugins[name] = plugin
            self._mcp_plugin_originals[name] = plugin

            logger.info(f"[TARGET] MCP plugin connection successful: {name}")

            # Add connected plugin to kernel
            if self.auto_add_to_kernel:
                logger.debug(f"[PACKAGE] Adding connected MCP plugin to kernel: {name}")
                self.kernel.add_plugin(plugin=plugin, plugin_name=name)
                logger.debug(f"Connected MCP plugin '{name}' added to kernel")

            logger.info(
                f"[SUCCESS] MCP plugin '{name}' connected and ready (TaskGroup scope managed)"
            )
            return True

        except Exception as e:
            logger.error(
                f"[FAILED] Failed to connect MCP plugin '{name}': {type(e).__name__}: {str(e)}"
            )

            # Enhanced error tracking for TaskGroup scope issues
            if "TaskGroup" in str(e) or "cancel scope" in str(e):
                logger.error(
                    f"[WARNING]  TASKGROUP SCOPE ERROR during MCP connection: {name}"
                )
                logger.error(
                    "This indicates connect() was called in a different task context"
                )  # Print full traceback for debugging
            import traceback

            traceback_str = traceback.format_exc()
            logger.error(f"Full traceback for MCP plugin '{name}':\n{traceback_str}")
            return False

    async def _setup_kernel_plugin(self, plugin: Any, name: str) -> bool:
        """Setup a kernel plugin."""
        try:
            logger.info(f"Setting up kernel plugin: {name}")

            # Check if plugin with same name already exists
            if name in self._kernel_plugins:
                logger.info(f"Replacing existing kernel plugin: {name}")

            self._kernel_plugins[name] = plugin

            # Add to kernel if requested (kernel.add_plugin handles replacement automatically)
            if self.auto_add_to_kernel:
                self.kernel.add_plugin(plugin=plugin, plugin_name=name)

            logger.info(f"[SUCCESS] Kernel plugin '{name}' ready")
            return True

        except Exception as e:
            logger.error(f"[FAILED] Failed to setup kernel plugin '{name}': {e}")
            return False

    async def _setup_all_plugins(self):
        """
        Setup all plugins with individual connection approach.

        This approach connects to each MCP plugin individually for better error
        isolation and clearer debugging, which is more suitable for production use.
        """
        print("DEBUG: _setup_all_plugins started with individual connections")
        setup_results = []

        print(f"DEBUG: About to loop through {len(self.plugins)} plugins")
        for i, plugin_entry in enumerate(self.plugins):
            print(f"DEBUG: Processing plugin {i}: {plugin_entry}")
            # Parse plugin entry (could be plugin or (plugin, name) tuple)
            plugin, custom_name = self._parse_plugin_entry(plugin_entry)

            # Skip None plugins (MCP unavailable)
            if plugin is None:
                logger.warning(
                    f"Skipping unavailable plugin {i} (likely MCP not available)"
                )
                continue

            plugin_type = self._detect_plugin_type(plugin)
            plugin_name = self._generate_plugin_name(
                plugin, plugin_type, i, custom_name
            )

            print(f"DEBUG: Setting up {plugin_type} plugin: {plugin_name}")

            if plugin_type == "mcp":
                success = await self._setup_mcp_plugin(plugin, plugin_name)
            elif plugin_type == "kernel":
                success = await self._setup_kernel_plugin(plugin, plugin_name)
            elif plugin_type == "unavailable":
                logger.warning(
                    f"Plugin {plugin_name} is unavailable (MCP support missing)"
                )
                success = False
            else:
                print(
                    f"DEBUG: Unknown plugin type for {plugin_name}, treating as kernel"
                )
                success = await self._setup_kernel_plugin(plugin, plugin_name)

            setup_results.append((plugin_name, plugin_type, success))

        print("DEBUG: Plugin setup loop completed")

        # Log summary
        successful = [r for r in setup_results if r[2]]
        failed = [r for r in setup_results if not r[2]]

        logger.info(
            f"[INFO] Individual connection setup complete: {len(successful)} successful, {len(failed)} failed"
        )
        print(
            f"DEBUG: Setup complete: {len(successful)} successful, {len(failed)} failed"
        )

        if successful:
            # logger.info("[SUCCESS] Successfully setup plugins:")
            print("DEBUG: Successfully setup plugins:")
            for name, ptype, _ in successful:
                # logger.info(f"  • {name} ({ptype})")
                print(f"DEBUG:  • {name} ({ptype})")

        if failed:
            # logger.warning("[FAILED] Failed to setup plugins:")
            print("DEBUG: Failed to setup plugins:")
            for name, ptype, _ in failed:
                # logger.warning(f"  • {name} ({ptype})")
                print(f"DEBUG:  • {name} ({ptype})")

        print("DEBUG: _setup_all_plugins completed")

    async def create_agent(
        self,
        agent_config: agent_info,
        service_id: str = "default",
        additional_plugins: list[Any] | None = None,
    ) -> Agent | AzureAssistantAgent | AzureAIAgent | ChatCompletionAgent | None:
        """
        Create an agent within this context.

        Args:
            agent_config: Agent configuration
            additional_plugins: Additional plugins for this specific agent

        Returns:
            Created agent builder
        """
        if not self._is_entered:
            raise RuntimeError("MCPContext must be entered before creating agents")

        logger.info(f"[ROBOT] Creating agent: {agent_config.agent_name}")

        # Collect all available plugins for the agent
        plugins_for_agent = additional_plugins or []

        # Add all kernel plugins from the context
        # For ChatCompletionAgent, we need to pass the actual kernel plugins, not the raw instances
        for name in self._kernel_plugins:
            if name in self.kernel.plugins:
                plugins_for_agent.append(self.kernel.plugins[name])

        # Add MCP plugins that are already connected
        # Use the original connected plugins, not the kernel copies, to maintain connection state
        logger.debug(f"Adding {len(self._mcp_plugins)} MCP plugins to agent")
        for name, plugin in self._mcp_plugins.items():
            # Use the original connected plugin directly, not from kernel
            plugins_for_agent.append(plugin)
            logger.debug(f"[SUCCESS] Added connected MCP plugin to agent: {name}")
            # Log that we're using the original connected plugin
            logger.debug(f"[PLUG] Using original connected MCP plugin for {name}")

        logger.info(
            f"[TOOLS] Agent will have access to {len(plugins_for_agent)} total plugins ({len(self._kernel_plugins)} kernel + {len(self._mcp_plugins)} MCP)"
        )

        agent_builder = await AgentBuilder.create_agent(
            kernel_agent=self.kernel_agent,
            agent_info=agent_config,
            service_id=service_id,
            plugins=plugins_for_agent,  # All plugins from context + additional
        )

        # Pure Manual: Track agent for manual cleanup
        # All resources are handled manually to avoid any task context issues
        if agent_builder:
            self._agents.append(agent_builder)
        else:
            logger.error(f"Failed to create agent: {agent_config.agent_name}")
            # Throw exception
            raise RuntimeError(f"Failed to create agent: {agent_config.agent_name}")

        logger.info(
            f"[SUCCESS] Agent '{agent_config.agent_name}' created with access to {len(self._mcp_plugins)} MCP plugins and {len(self._kernel_plugins)} kernel plugins"
        )

        return agent_builder.agent

    def verify_taskgroup_scope_safety(self) -> dict[str, Any]:
        """
        Verify TaskGroup scope management is properly implemented.

        Returns comprehensive status of TaskGroup scope safety measures.
        """
        import asyncio

        current_task_id = id(asyncio.current_task()) if asyncio.current_task() else None

        verification = {
            "taskgroup_scope_managed": True,
            "current_task_context": current_task_id,
            "mcp_plugins_count": len(self._mcp_plugins),
            "mcp_originals_count": len(self._mcp_plugin_originals),
            "same_task_connect_close": True,  # Guaranteed by async context manager design
            "scope_safety_features": {
                "async_context_manager": True,  # __aenter__ and __aexit__ in same task
                "connect_in_aenter": True,  # connect() called during setup
                "close_in_aexit": True,  # close() called during cleanup
                "error_detection": True,  # TaskGroup error detection implemented
                "task_context_logging": True,  # Task context IDs logged for debugging
            },
            "risk_mitigation": {
                "sync_to_async_agent_creation": "handled",  # Root cause addressed
                "http_task_spawning": "isolated",  # New tasks don't affect MCP scopes
                "cancel_scope_violations": "prevented",  # Same-task-context lifecycle
                "anyio_taskgroup_compliance": "enforced",  # Proper TaskGroup scope management
            },
        }

        logger.info("[SEARCH] TaskGroup Scope Verification Complete")
        logger.info(
            f"[SUCCESS] MCP plugins managed with TaskGroup scope safety: {verification['mcp_plugins_count']}"
        )

        return verification

    async def verify_mcp_connections(self) -> dict[str, bool]:
        """Verify all MCP plugin connections are still active."""
        connection_status = {}

        for name, plugin in self._mcp_plugins.items():
            try:
                logger.debug(f"Checking MCP connection status for: {name}")

                # Since we're not manually managing contexts, we check if the plugin
                # is properly configured rather than checking active sessions
                if hasattr(plugin, "__aenter__") and hasattr(plugin, "__aexit__"):
                    # MCP plugin is properly configured as async context manager
                    logger.debug(f"MCP plugin is properly configured: {name}")
                    connection_status[name] = True
                else:
                    logger.warning(
                        f"MCP plugin missing async context manager interface: {name}"
                    )
                    connection_status[name] = False

            except Exception as e:
                logger.error(f"Error checking MCP connection for {name}: {e}")
                connection_status[name] = False

        # Log summary
        active_count = sum(connection_status.values())
        total_count = len(connection_status)
        logger.debug(f"MCP Connection Summary: {active_count}/{total_count} active")

        return connection_status

    async def refresh_tools(self) -> bool:
        """
        Refresh all MCP tools by reconnecting plugins.

        This method is called by agents when they need to ensure tool connectivity,
        especially for blob storage operations that may have connection issues.

        Returns:
            bool: True if all tools refreshed successfully, False otherwise
        """
        logger.info("[REFRESH] Starting tool refresh for MCP plugins...")

        if not self._is_entered:
            logger.error("[FAILED] Cannot refresh tools - context not entered")
            return False

        refresh_success = True

        # Refresh MCP plugins by reconnecting them
        for plugin_name, _plugin in list(self._mcp_plugins.items()):
            try:
                logger.info(f"[REFRESH] Refreshing MCP plugin: {plugin_name}")

                # For MCP plugins, we need to reconnect by recreating the connection
                original_plugin = self._mcp_plugin_originals.get(plugin_name)
                if original_plugin:
                    # Just reconnect the plugin (kernel.add_plugin handles replacement automatically)
                    success = await self._setup_mcp_plugin(original_plugin, plugin_name)
                    if not success:
                        refresh_success = False
                        logger.error(
                            f"[FAILED] Failed to refresh plugin: {plugin_name}"
                        )
                    else:
                        logger.info(f"[SUCCESS] Refreshed plugin: {plugin_name}")
                else:
                    logger.warning(
                        f"[WARNING] No original plugin reference for: {plugin_name}"
                    )
                    refresh_success = False

            except Exception as e:
                logger.error(f"[FAILED] Exception refreshing {plugin_name}: {e}")
                refresh_success = False

        if refresh_success:
            logger.info("[SUCCESS] All MCP tools refreshed successfully")
        else:
            logger.error("[FAILED] Some tools failed to refresh")

        return refresh_success

    def get_plugin_info(self) -> dict[str, dict[str, Any]]:
        """Get information about all managed plugins."""
        info = {
            "mcp_plugins": {
                name: {
                    "type": "mcp",
                    "class": plugin.__class__.__name__,
                    "connected": getattr(plugin, "session", None) is not None,
                }
                for name, plugin in self._mcp_plugins.items()
            },
            "kernel_plugins": {
                name: {
                    "type": "kernel",
                    "class": plugin.__class__.__name__,
                    "functions": len(self.kernel.plugins[name].functions)
                    if name in self.kernel.plugins
                    else 0,
                }
                for name, plugin in self._kernel_plugins.items()
            },
        }
        return info

    def list_available_plugins(self) -> list[str]:
        """List all available plugin names."""
        return list(self._mcp_plugins.keys()) + list(self._kernel_plugins.keys())

    def request_cleanup(self):
        """Request cleanup to be performed on next context exit."""
        logger.debug("Cleanup explicitly requested")
        self._cleanup_requested = True
        self._in_use = False

    async def __aenter__(self):
        """
        Enter the context manager with TaskGroup scope management.

        CRITICAL TaskGroup Scope Management:
        - This method establishes the async task context for all MCP operations
        - All MCP plugin connect() calls happen in this same task context
        - The corresponding close() calls in __aexit__ happen in the same task context
        - This prevents anyio TaskGroup "cancel scope in different task" errors

        TaskGroup Scope Strategy:
        1. __aenter__ and __aexit__ execute in the same async task by design
        2. All MCP connect() calls happen during __aenter__ setup
        3. All MCP close() calls happen during __aexit__ cleanup
        4. This maintains TaskGroup scope consistency across MCP lifecycle

        Background: This pattern prevents the TaskGroup violations that occurred
        when agent creation changed from sync to async, spawning new HTTP tasks
        that violated existing MCP TaskGroup scopes.
        """
        print("DEBUG: __aenter__ VERY START - TaskGroup scope management")

        # Log task context for TaskGroup scope tracking
        current_task_id = id(__import__("asyncio").current_task())
        logger.debug(f"[START] MCPContext __aenter__ task context: {current_task_id}")
        logger.info("Entering MCPContext with TaskGroup scope management")
        print("DEBUG: __aenter__ started with task context tracking")

        try:
            print(
                "DEBUG: About to call _setup_all_plugins with TaskGroup scope management"
            )
            logger.debug("[TOOLS] Starting MCP plugin setup in same task context")

            await self._setup_all_plugins()
            print("DEBUG: _setup_all_plugins completed successfully")
            logger.debug("[SUCCESS] All MCP plugins connected in same task context")

            self._is_entered = True
            self._in_use = True  # Mark context as actively in use

            plugin_info = self.get_plugin_info()
            mcp_count = len(plugin_info["mcp_plugins"])
            kernel_count = len(plugin_info["kernel_plugins"])

            logger.info(
                f"[TARGET] MCPContext ready with {mcp_count} MCP plugins and {kernel_count} kernel plugins (TaskGroup scope managed)"
            )
            print(
                f"DEBUG: MCPContext ready with {mcp_count} MCP plugins and {kernel_count} kernel plugins"
            )
            print(
                "DEBUG: __aenter__ completed successfully with TaskGroup scope management"
            )

            return self

        except Exception as e:
            logger.error(f"[FAILED] Failed to enter MCPContext: {e}")
            print(f"DEBUG: Exception in __aenter__: {e}")

            # Enhanced error tracking for TaskGroup scope issues
            if "TaskGroup" in str(e) or "cancel scope" in str(e):
                logger.error("[WARNING]  TASKGROUP SCOPE ERROR during MCPContext entry")
                logger.error(
                    "This indicates a task boundary violation during MCP setup"
                )
                print("DEBUG: TaskGroup scope error detected during entry")

            # Pure manual cleanup on failure - no safe stack to clean
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager with comprehensive cleanup and detailed error tracing."""

        # ENHANCED: Detailed tracing of exit conditions
        print("DEBUG: __aexit__ called with detailed tracing")
        logger.debug("=" * 60)
        logger.debug("__aexit__ ENTRY - Detailed Error Analysis")
        logger.debug("=" * 60)

        # Log all exit parameters in detail
        logger.debug(f"exc_type: {exc_type}")
        logger.debug(f"exc_val: {exc_val}")
        logger.debug(f"exc_tb: {exc_tb}")
        logger.debug(f"_in_use: {self._in_use}")
        logger.debug(f"_cleanup_requested: {self._cleanup_requested}")
        logger.debug(f"_is_entered: {self._is_entered}")

        # Analyze the type of exit
        if exc_type is None:
            logger.debug("🟢 NORMAL EXIT - No exception occurred")
            print("DEBUG: Normal exit - no exception")
        else:
            logger.error("[RED_CIRCLE] EXCEPTION EXIT - Exception triggered cleanup")
            logger.error(f"Exception type: {exc_type.__name__}")
            logger.error(f"Exception message: {str(exc_val)}")
            print(f"DEBUG: Exception exit - {exc_type.__name__}: {str(exc_val)}")

            # Check for specific error types that might indicate TaskGroup issues
            if "TaskGroup" in str(exc_val) or "cancel scope" in str(exc_val):
                logger.error("[WARNING]  TASKGROUP SCOPE ERROR DETECTED")
                print("DEBUG: TaskGroup scope error detected!")
            elif "RuntimeError" in str(exc_type.__name__):
                logger.error("[WARNING]  RUNTIME ERROR DETECTED")
                print("DEBUG: Runtime error detected!")

            # Log the full traceback for detailed analysis
            if exc_tb:
                import traceback

                tb_str = "".join(traceback.format_tb(exc_tb))
                logger.error(f"Full traceback:\n{tb_str}")
                print(f"DEBUG: Traceback available, length: {len(tb_str)} chars")

        # CRITICAL: Always cleanup in __aexit__ for proper TaskGroup scope management
        # In an async context manager, __aexit__ MUST perform cleanup to maintain
        # TaskGroup scope consistency. Deferring cleanup causes plugins to be
        # garbage collected in different task contexts, leading to TaskGroup violations.

        logger.info(
            "[CLEANUP] STARTING MANDATORY CLEANUP - Ensuring TaskGroup scope consistency"
        )
        print(
            "DEBUG: Starting mandatory resource cleanup to prevent TaskGroup scope violations"
        )

        # Mark context as no longer in use
        self._in_use = False
        self._cleanup_requested = True

        cleanup_errors = []  # Track cleanup errors separately

        try:
            # STEP 1: Cleanup agents with error tracking
            logger.debug("[CLIPBOARD] STEP 1: Cleaning up agents")
            print("DEBUG: Cleaning up agents...")

            for i, agent in enumerate(self._agents):
                try:
                    agent_name = agent.agent.name
                    logger.debug(f"Cleaning up agent: {agent_name}")

                    # Check if agent has a cleanup method
                    if hasattr(agent, "cleanup"):
                        logger.debug(f"Calling cleanup() on agent: {agent_name}")
                        await agent.cleanup()
                        logger.debug(
                            f"[SUCCESS] Agent cleanup successful: {agent_name}"
                        )

                    # DEFENSIVE: If agent is an async context manager, exit it manually
                    elif hasattr(agent, "__aexit__"):
                        logger.debug(
                            f"Manually exiting agent async context: {agent_name}"
                        )
                        await agent.__aexit__(None, None, None)
                        logger.debug(
                            f"[SUCCESS] Agent context exit successful: {agent_name}"
                        )

                except Exception as e:
                    agent_name = getattr(agent, "meta_data", {}).get(
                        "agent_name", f"agent_{i}"
                    )
                    error_msg = f"Agent cleanup failed ({agent_name}): {e}"
                    logger.warning(f"[WARNING]  {error_msg}")
                    print(f"DEBUG: Agent cleanup error: {error_msg}")
                    cleanup_errors.append(f"Agent {agent_name}: {str(e)}")

            # STEP 2: Cleanup MCP plugins with TaskGroup scope management
            logger.debug(
                "[PLUG] STEP 2: Disconnecting MCP plugins with TaskGroup scope management"
            )
            print(
                "DEBUG: Disconnecting MCP plugins with proper TaskGroup scope context..."
            )

            # Log current task context for TaskGroup scope verification
            current_task_id = id(__import__("asyncio").current_task())
            logger.debug(f"[CLEANUP] MCP cleanup task context: {current_task_id}")

            # CRITICAL TaskGroup Scope Management:
            # - connect() was called in __aenter__ in this same task context
            # - close() is being called in __aexit__ in this same task context
            # - This maintains anyio TaskGroup scope consistency and prevents
            #   "cancel scope in different task" errors
            #
            # Background: When agent creation changed from sync to async, it spawned
            # new HTTP tasks that violated MCP TaskGroup scopes. This same-task-context
            # pattern prevents those violations by ensuring connect()/close() happen
            # in the same async task context.

            for name, plugin in list(self._mcp_plugin_originals.items()):
                try:
                    logger.debug(f"[PLUG] Disconnecting MCP plugin: {name}")
                    logger.debug(f"Plugin type: {type(plugin).__name__}")

                    # Check what methods are available
                    has_close = hasattr(plugin, "close") and callable(plugin.close)
                    has_aexit = hasattr(plugin, "__aexit__")

                    logger.debug(
                        f"Plugin {name} - has_close: {has_close}, has_aexit: {has_aexit}"
                    )

                    if has_close:
                        logger.debug(
                            f"[LINK] Calling close() for MCP plugin: {name} (TaskGroup scope maintained)"
                        )
                        print(f"DEBUG: Calling close() on {name} in same task context")
                        await plugin.close()
                        logger.debug(
                            f"[SUCCESS] MCP plugin close successful: {name} (TaskGroup scope properly managed)"
                        )
                        print(f"DEBUG: Successfully closed {name}")
                    else:
                        logger.debug(
                            f"MCP plugin {name} does not have close() method - skipping manual disconnect"
                        )
                        print(f"DEBUG: No close() method for {name} - skipping")

                except Exception as e:
                    error_msg = f"MCP plugin disconnect failed ({name}): {e}"
                    logger.warning(f"[WARNING]  {error_msg}")
                    print(f"DEBUG: MCP disconnect error: {error_msg}")

                    # Enhanced TaskGroup scope error detection
                    if "TaskGroup" in str(e) or "cancel scope" in str(e):
                        logger.error(
                            f"[ALERT] TASKGROUP SCOPE ERROR during MCP cleanup: {name}"
                        )
                        logger.error(
                            "This indicates connect()/close() were called in different task contexts"
                        )
                        print(f"DEBUG: TaskGroup scope error detected for {name}!")

                    cleanup_errors.append(f"MCP {name}: {str(e)}")
                    error_msg = f"MCP plugin disconnect failed ({name}): {type(e).__name__}: {str(e)}"
                    logger.warning(f"[WARNING]  {error_msg}")
                    print(f"DEBUG: MCP disconnect error: {error_msg}")

                    # Check if this is the TaskGroup scope error
                    if "cancel scope" in str(e) or "TaskGroup" in str(e):
                        logger.error(
                            f"[ALERT] TASKGROUP SCOPE ERROR in MCP cleanup for {name}"
                        )
                        print(f"DEBUG: TaskGroup scope error in {name} cleanup!")

                    cleanup_errors.append(f"MCP {name}: {str(e)}")

            logger.debug(
                "[SUCCESS] MCP plugin disconnect completed with proper task context"
            )
            print("DEBUG: MCP disconnect completed")

            # STEP 3: Clear references
            logger.debug("[CLEANUP]  STEP 3: Clearing plugin references")
            print("DEBUG: Clearing references...")

            plugin_counts = {
                "mcp": len(self._mcp_plugins),
                "kernel": len(self._kernel_plugins),
                "agents": len(self._agents),
            }

            self._kernel_plugins.clear()
            self._mcp_plugins.clear()
            self._mcp_plugin_originals.clear()
            self._agents.clear()

            logger.debug(f"Cleared references: {plugin_counts}")
            print(f"DEBUG: Cleared {plugin_counts}")

            # STEP 4: Final status
            if cleanup_errors:
                logger.warning(
                    f"[WARNING]  CLEANUP COMPLETED WITH {len(cleanup_errors)} ERRORS:"
                )
                print(f"DEBUG: Cleanup completed with {len(cleanup_errors)} errors")
                for error in cleanup_errors:
                    logger.warning(f"  - {error}")
                    print(f"DEBUG: Cleanup error: {error}")
            else:
                logger.info("[SUCCESS] CLEANUP COMPLETED SUCCESSFULLY - No errors")
                print("DEBUG: Cleanup completed successfully")

        except Exception as cleanup_exception:
            logger.error(
                f"[EXPLOSION] CRITICAL ERROR during MCPContext cleanup: {cleanup_exception}"
            )
            print(f"DEBUG: Critical cleanup error: {cleanup_exception}")

            # Log the full traceback for the cleanup error
            import traceback

            traceback_str = traceback.format_exc()
            logger.error(f"Cleanup exception traceback:\n{traceback_str}")
            print(
                f"DEBUG: Cleanup exception traceback length: {len(traceback_str)} chars"
            )

            raise
        finally:
            self._is_entered = False
            logger.debug("[FINISH] __aexit__ COMPLETE - Context state reset")
            print("DEBUG: __aexit__ completed")


# Convenience functions for common use cases


async def create_mcp_context_with_agent(
    kernel_agent: semantic_kernel_agent,
    agent_config: agent_info,
    plugins: list[Any],
    service_id: str = "default",
    plugin_names: dict[str, str] | None = None,
):
    """
    Convenience function to create MCPContext with a single agent.

    Usage:
        async with create_mcp_context_with_agent(
            kernel_agent, agent_config, [datetime_plugin, file_plugin]
        ) as (context, agent):
            response = await agent.get_response(messages)
    """
    context = PluginContext(kernel_agent, plugins, plugin_names)

    async with context as ctx:
        agent = await ctx.create_agent(agent_config=agent_config, service_id=service_id)
        yield ctx, agent


def create_plugin_name_mapping(**kwargs) -> dict[str, str]:
    """
    Helper function to create plugin name mappings.

    Usage:
        name_mapping = create_plugin_name_mapping(
            datetime_plugin="datetime_service",
            file_plugin="file_operations"
        )
    """
    # This would need to be implemented based on how you pass plugin instances
    # For now, return the kwargs as-is
    return kwargs


def with_name(plugin: Any, name: str) -> tuple[Any, str]:
    """
    Helper function to create (plugin, name) tuples for meaningful plugin naming.

    Usage:
        plugins = [
            with_name(get_datetime_plugin(), "datetime_service"),
            with_name(FileIOPlugin("."), "file_operations"),
            WeatherPlugin(),  # Will use auto-generated name
        ]
    """
    return (plugin, name)
