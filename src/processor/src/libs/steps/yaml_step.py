"""
YAML Step - Single responsibility: Convert configuration files to Azure format.

Following SK Process Framework best practices:
- Single responsibility principle
- Proper event handling with error management
- Isolated kernel instance
- Clear input/output via events
- Step-specific group chat orchestration
"""

from datetime import time
import logging
import time
from typing import TYPE_CHECKING, Any

from jinja2 import Template
from pydantic import Field
from semantic_kernel.agents import GroupChatOrchestration

# Run the orchestration with the rendered task
from semantic_kernel.agents.runtime import InProcessRuntime
from semantic_kernel.contents import ChatMessageContent
from semantic_kernel.functions import kernel_function
from semantic_kernel.processes.kernel_process import (
    KernelProcessStep,
    KernelProcessStepContext,
    KernelProcessStepState,
)

from libs.steps.base_step_state import BaseStepState

if TYPE_CHECKING:
    from libs.models.failure_context import StepFailureState

from libs.base.KernelAgent import semantic_kernel_agent
from libs.steps.orchestration.models.yaml_result import (
    ConvertedFile,
    Yaml_ExtendedBooleanResult,
)
from libs.steps.orchestration.yaml_orchestration import (
    YamlOrchestrator,
)
from libs.steps.step_failure_collector import StepFailureCollector
from plugins.mcp_server import MCPBlobIOPlugin, MCPDatetimePlugin, MCPMicrosoftDocs
from utils.agent_telemetry import (
    TelemetryManager,
)
from utils.logging_utils import create_migration_logger, safe_log
from utils.mcp_context import PluginContext, with_name
from utils.tool_tracking import ToolTrackingMixin

logger = create_migration_logger(__name__)


class YamlStepState(BaseStepState):
    """State for the YAML step following best practices."""

    # Base fields required by KernelProcessStepState
    name: str = Field(default="YamlStepState", description="Name of the step state")
    version: str = Field(default="1.0", description="Version of the step state")
    result: bool | None = None  # None = not started, True = success, False = failed
    yaml_conversions: list[str] = []
    converted_files: list[ConvertedFile] = []
    yaml_completed: bool = False
    final_result: Yaml_ExtendedBooleanResult | None = None
    reason: str = Field(default="", description="Reason for failure if any")

    requires_immediate_retry: bool = Field(default=False)
    termination_details: dict[str, Any] | None = Field(default=None)

    # # NEW: Rich failure context for unhappy path
    # failure_context: StepFailureState | None = Field(
    #     default=None, description="Rich failure context when step fails"
    # )
    # execution_start_time: float | None = Field(
    #     default=None, description="When step execution started"
    # )


class YamlStep(KernelProcessStep[YamlStepState], ToolTrackingMixin):
    """
    YAML step that converts configuration files to Azure format.

    Following SK Process Framework best practices:
    - Single responsibility: YAML conversion only
    - Isolated kernel instance to prevent recursive invocation
    - Proper error handling and event emission
    - Simple, focused functionality
    """

    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}

    state: YamlStepState | None = Field(
        default_factory=lambda: YamlStepState(name="YamlStepState", version="1.0")
    )

    def create_task_local_mcp_context(self) -> PluginContext:
        """
        Create task-local MCP context for TaskGroup-safe operations.

        CRITICAL: This context must be used with async context manager pattern
        within the same async task to prevent TaskGroup scope violations.

        Usage pattern:
            async with self.create_task_local_mcp_context() as mcp_context:
                # Use mcp_context within this task only
                pass
        """
        if self.kernel_agent is None:
            raise RuntimeError("Kernel agent not initialized")

        return PluginContext(
            kernel_agent=self.kernel_agent,
            plugins=[
                plugin_spec
                for plugin_spec in [
                    with_name(MCPDatetimePlugin.get_datetime_plugin(), "datetime"),
                    with_name(MCPBlobIOPlugin.get_blob_file_operation_plugin(), "blob"),
                    with_name(MCPMicrosoftDocs.get_microsoft_docs_plugin(), "msdocs"),
                ]
                if plugin_spec[0] is not None  # Filter out None plugins
            ],
        )

    def __init__(self):
        """Initialize synchronously - async work happens in activate().

        Args:
            telemetry: Optional telemetry instance for tracking. If None, uses global functions.
            **kwargs: Additional arguments passed to parent class
        """
        super().__init__()
        logger.info(
            "[TOOLS] YAML STEP CONSTRUCTOR: Starting synchronous initialization..."
        )
        self.kernel_agent = None
        self._orchestrator: GroupChatOrchestration | None = None

        # No shared MCP context - this step creates its own

        logger.info(
            "[SUCCESS] YAML STEP CONSTRUCTOR: Synchronous initialization complete"
        )

    async def activate(self, state: KernelProcessStepState[YamlStepState]):
        """
        Activate the step for state initialization only.

        Note: Kernel agent creation moved to start_yaml_from_design() for lazy initialization.
        This avoids unnecessary resource allocation for steps that may never execute.
        """
        self.state = state.state
        # Ensure state is never None
        self._ensure_state_initialized()

    def _ensure_state_initialized(self) -> None:
        """Ensure state is properly initialized before use."""
        if self.state is None:
            self.state = YamlStepState(name="YamlStepState", version="1.0")

    def _extract_comprehensive_step_parameters(
        self, context_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Extract comprehensive parameters from context data with intelligent fallback strategy.

        YAML step receives Design step results in context_data structure:
        {
            "process_id": "...",
            "analysis_result": {
                "state": Analysis_ExtendedBooleanResult {
                    "termination_output": AnalysisOutput {...}
                }
            },
            "design_result": {
                "state": Design_ExtendedBooleanResult {
                    "termination_output": DesignOutput {...}
                }
            }
        }

        Fallback strategy for missing data:
        1. Try to get from design step output
        2. Try to get from analysis step data (if preserved in context)
        3. Use intelligent defaults
        """
        # Basic parameters
        design_result = context_data.get("design_result", {})
        analysis_result = context_data.get("analysis_result", {})

        # Extract design step results from design_result.state.termination_output
        design_state = design_result.get(
            "state"
        )  # This is Design_ExtendedBooleanResult
        design_output = None

        if design_state and hasattr(design_state, "termination_output"):
            design_output = design_state.termination_output
        elif design_state and isinstance(design_state, dict):
            design_output = design_state.get("termination_output")

        # Extract analysis results from analysis_result.state.termination_output
        analysis_state = analysis_result.get(
            "state"
        )  # This is Analysis_ExtendedBooleanResult
        analysis_output = None

        if analysis_state and hasattr(analysis_state, "termination_output"):
            analysis_output = analysis_state.termination_output
        elif analysis_state and isinstance(analysis_state, dict):
            analysis_output = analysis_state.get("termination_output")

        # Extract files_count with intelligent fallback and error handling
        discovered_files_raw = analysis_result.get("discovered_files")
        if discovered_files_raw is None:
            files_count = 0
            discovered_files_list = []
            logger.warning(
                f"[WARNING] No discovered_files found in analysis_result for process {context_data.get('process_id', 'unknown')}"
            )
        else:
            files_count = len(discovered_files_raw)
            discovered_files_list = discovered_files_raw

        # Try 1: Get from design output

        # Extract complexity_analysis with fallback
        complexity_analysis = {}

        # Try 1: Get from design output
        complexity_analysis = self._safe_get_dict_value(
            design_output, "complexity_analysis", {}
        )

        # Try 2: Get from analysis output
        if not complexity_analysis and analysis_output:
            complexity_analysis = self._safe_get_dict_value(
                analysis_output, "complexity_analysis", {}
            )

        # Try 3: Create basic structure from available data
        if not complexity_analysis:
            complexity_analysis = {
                "network": "Unknown",
                "security": "Unknown",
                "storage": "Unknown",
                "compute": "Unknown",
            }

        # Extract migration_readiness_score with fallback
        # migration_readiness_score = "Medium"

        # Fix: Access Pydantic model attributes directly with null checks
        if analysis_output is not None:
            migration_readiness_score = (
                analysis_output.migration_readiness.overall_score
            )
            source_platform = analysis_output.platform_detected
            source_platform_confidence = analysis_output.confidence_score
        else:
            migration_readiness_score = "Medium"
            source_platform = "Unknown"
            source_platform_confidence = "50%"
        # migration_readiness_score = self._safe_get_value(
        #     design_output, "migration_readiness_score", "Medium"
        # )

        # Try 2: Get from analysis output migration_readiness.overall_score
        # if migration_readiness_score == "Medium" and analysis_output:
        #     migration_readiness = self._safe_get_dict_value(
        #         analysis_output, "migration_readiness", {}
        #     )
        #     if migration_readiness:
        #         migration_readiness_score = self._safe_get_value(
        #             migration_readiness, "overall_score", "Medium"
        #         )

        # Build comprehensive parameter set
        parameters = {
            # Basic process parameters
            "process_id": context_data.get("process_id"),
            "source_file_folder": analysis_result.get(
                "source_file_folder", "source"
            ),  # mistake. design_result doesn't ship source_file_folder. need to be updated.
            "output_file_folder": design_result.get("output_file_folder", "converted"),
            "workspace_file_folder": design_result.get(
                "workspace_file_folder", "workspace"
            ),
            "container_name": design_result.get("container_name", "processes"),
            # Design step context with null checks
            "azure_services": design_output.azure_services if design_output else [],
            "azure_services_count": len(design_output.azure_services)
            if design_output
            else 0,
            "architecture_decisions": design_output.architecture_decisions
            if design_output
            else [],
            "design_summary": design_output.summary
            if design_output
            else "No design summary available",
            # Analysis context with intelligent fallback
            "source_platform": source_platform,
            "platform_confidence": source_platform_confidence,
            # Intelligent fallback parameters
            "files_count": files_count,
            "discovered_files_list": discovered_files_list,
            "migration_readiness_score": migration_readiness_score,
            "complexity_analysis": complexity_analysis,
            # Full design data access for advanced scenarios
            "full_design_data": design_output,
            "full_analysis_data": analysis_output,
        }

        return parameters

    def _safe_get_value(self, obj: Any, field_name: str, default: str) -> str:
        """Safely extract values from either dict or Pydantic model."""
        if not obj:
            return default
        if isinstance(obj, dict):
            return obj.get(field_name, default)
        elif hasattr(obj, field_name):
            return getattr(obj, field_name, default)
        else:
            return default

    def _safe_get_list_value(self, obj: Any, field_name: str, default: list) -> list:
        """Safely extract list values from either dict or Pydantic model."""
        if not obj:
            return default
        if isinstance(obj, dict):
            return obj.get(field_name, default)
        elif hasattr(obj, field_name):
            return getattr(obj, field_name, default)
        else:
            return default

    def _safe_get_dict_value(self, obj: Any, field_name: str, default: dict) -> dict:
        """Safely extract dict values from either dict or Pydantic model."""
        if not obj:
            return default
        if isinstance(obj, dict):
            return obj.get(field_name, default)
        elif hasattr(obj, field_name):
            return getattr(obj, field_name, default)
        else:
            return default

    def _safe_get_int_value(self, obj: Any, field_name: str, default: int) -> int:
        """Safely extract integer values from either dict or Pydantic model."""
        if not obj:
            return default

        value = None
        if isinstance(obj, dict):
            value = obj.get(field_name)
        elif hasattr(obj, field_name):
            value = getattr(obj, field_name)

        if value is None:
            return default

        # Try to convert to int
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def _safe_get_value_with_fallback(
        self, primary_obj: Any, fallback_obj: Any, field_name: str, default: str
    ) -> str:
        """Safely extract values with fallback from either dict or Pydantic model."""
        # Try primary object first
        value = self._safe_get_value(primary_obj, field_name, "")
        if value and value != "":
            return value

        # Try fallback object
        value = self._safe_get_value(fallback_obj, field_name, "")
        if value and value != "":
            return value

        # Return default
        return default

    def _create_termination_context_data(self, yaml_output) -> dict[str, Any]:
        """Create context data for termination failure scenarios"""
        context_data = {
            "termination_type": yaml_output.termination_type,
            "termination_reason": yaml_output.reason,
            "blocking_issues": list(yaml_output.blocking_issues) if yaml_output.blocking_issues else [],
        }

        # Add termination output details if available
        if yaml_output.termination_output:
            context_data.update({
                "converted_files": yaml_output.termination_output.converted_files or [],
                "expert_insights": yaml_output.termination_output.expert_insights or [],
                "conversion_summary": yaml_output.termination_output.conversion_summary or {},
            })

        return context_data

    async def _process_hard_termination_as_failure(
        self, yaml_output, process_id: str
    ) -> None:
        """Process ALL hard terminations as permanent failures using existing error infrastructure"""
        # Extract converted files safely
        converted_files = (
            yaml_output.termination_output.converted_files or []
            if yaml_output.termination_output
            else []
        )

        # Step 1: Update telemetry with failure notification
        await self.telemetry.update_agent_activity(
            process_id,
            "Conversation_Manager",
            "yaml_permanently_failed",
            f"YAML conversion failed permanently due to {yaml_output.termination_type}: {yaml_output.reason}. Expert consensus: {yaml_output.blocking_issues}"
        )

        # Step 2: Create failure context using existing StepFailureCollector
        # Create "virtual exception" for termination scenario
        termination_error = ValueError(f"Hard termination: {yaml_output.termination_type} - {yaml_output.reason}")

        # Use existing StepFailureCollector
        failure_collector = StepFailureCollector()
        system_context = await failure_collector.collect_system_failure_context(
            error=termination_error,
            step_name="YamlStep",
            process_id=process_id,
            context_data=self._create_termination_context_data(yaml_output),
            step_start_time=self.state.execution_start_time,
            step_phase="hard_termination_yaml"
        )

        # Step 3: Set failure state (NOT retry state)
        self._ensure_state_initialized()
        assert self.state is not None  # For type checker

        # Set up basic state (similar to current logic but as FAILURE)
        self.state.name = "YamlStepState"
        self.state.id = "Yaml"
        self.state.version = "1.0"
        self.state.result = False  # FAILURE, not retry
        self.state.yaml_completed = False
        self.state.converted_files = converted_files
        self.state.yaml_conversions = (
            yaml_output.termination_output.expert_insights or []
            if yaml_output.termination_output
            else []
        )
        self.state.final_result = yaml_output
        self.state.reason = f"Hard termination: {yaml_output.termination_type} - {yaml_output.reason}"

        # Set failure context using existing infrastructure
        self.state.failure_context = await failure_collector.create_step_failure_state(
            reason=f"YAML conversion terminated: {yaml_output.termination_type} - {yaml_output.reason}",
            execution_time=self.state.total_execution_duration or 0.0,
            files_attempted=converted_files,
            system_failure_context=system_context
        )

        # CRITICAL: Do NOT set retry flags
        # self.state.requires_immediate_retry = False (default)
        # No termination_details for retry

        # Step 4: Record failure outcome in telemetry
        failure_details = {
            "termination_type": yaml_output.termination_type,
            "termination_reason": yaml_output.reason,
            "blocking_issues": yaml_output.blocking_issues,
            "converted_files": len(converted_files),
            "handled_as": "permanent_failure"
        }

        await self.telemetry.update_agent_activity(
            process_id,
            "YAML_Expert",
            "step_permanently_failed",
            f"YAML step terminated permanently: {failure_details}"
        )

    @kernel_function(description="Handle YAML conversion event from design completion")
    async def start_yaml_from_design(
        self, context: KernelProcessStepContext, context_data: dict[str, Any]
    ) -> None:
        """
        Handle the DesignCompleted event and delegate to execute_yaml_conversion.

        This function extracts parameters from the context_data and calls execute_yaml_conversion.
        Each step creates its own PluginContext for clean isolation.
        """
        # Extract process_id for telemetry tracking
        process_id = context_data.get("process_id", "default-process-id")
        app_context = context_data.get("app_context")
        self.telemetry = TelemetryManager(app_context)

        try:
            logger.info(
                "[START] Received DesignCompleted event, starting YAML conversion with lazy kernel agent initialization..."
            )

            # NEW: Use comprehensive timing infrastructure for execution tracking
            self._ensure_state_initialized()
            assert self.state is not None  # For type checker
            self.state.set_execution_start()

            # Lazy initialization: Create kernel agent only when step actually needs to execute
            if self.kernel_agent is None:
                logger.info("[TOOLS] YAML STEP: Creating kernel agent for execution...")
                self.kernel_agent = semantic_kernel_agent(
                    env_file_path=None,  # Do not load .env file
                    custom_service_prefixes=None,
                    use_entra_id=True,
                )
                logger.info("[TOOLS] YAML STEP: About to initialize kernel agent...")
                await self.kernel_agent.initialize_async()
                logger.info("[SUCCESS] YAML STEP: Kernel agent ready for execution")

            logger.info(
                "[SUCCESS] YAML STEP ACTIVATE: Step state initialized (kernel agent will be created when needed)"
            )

            # Transition to YAML phase
            if self.telemetry:
                await self.telemetry.transition_to_phase(
                    process_id=process_id, phase="YAML", step="YAML"
                )
                await self.telemetry.complete_all_participant_agents(
                    process_id=process_id
                )
                await self.telemetry.update_agent_activity(
                    process_id=process_id,
                    agent_name="Conversation_Manager",
                    action="expert_yaml_starting",
                    message_preview="Starting expert YAML conversion discussion",
                )

            # Initialize step-level telemetry - moved here as this is when step actually starts
            await self.telemetry.update_agent_activity(
                process_id=process_id,
                agent_name="Conversation_Manager",
                action="expert_step_initializing",
                message_preview=f"Expert YAML discussion starting for process {process_id}",
            )

            # Update agent activity with instance telemetry if available
            await self.telemetry.update_agent_activity(
                process_id=process_id,
                agent_name="Conversation_Manager",
                action="expert_step_starting",
                message_preview="Starting expert YAML conversion discussion for Azure configuration files",
            )

            # Extract parameters from context_data
            process_id = context_data.get("process_id", "default-process-id")
            previous_result = context_data.get("analysis_result", {})
            source_file_folder = previous_result.get("source_file_folder", "source")
            output_file_folder = previous_result.get("output_file_folder", "converted")

            # Initialize step-specific group chat orchestrator
            # process_context = {
            #     "source_file_folder": source_file_folder,
            #     "output_file_folder": output_file_folder,
            #     "workspace_folder": workspace_folder,
            #     "container_name": "processes",
            #     "process_id": process_id,
            # }

            async def agent_response_callback(message: ChatMessageContent):
                # Handle agent responses specific to the YAML step
                try:
                    agent_name = getattr(message, "name", "Unknown_Agent")
                    content = getattr(message, "content", "No content")

                    print(f"🔧 [YAML CALLBACK] Agent: {agent_name}")
                    print(f"🔧 [YAML CALLBACK] Content: {content[:200]}...")

                    # Enhanced tool usage detection and tracking
                    await self.detect_and_track_tool_usage(
                        process_id, agent_name, content
                    )

                    # Also log to telemetry if available
                    await self.telemetry.update_agent_activity(
                        process_id=process_id,
                        agent_name=agent_name,
                        action="yaml_response",
                        message_preview=f"YAML phase response: {content[:200]}...",
                    )
                except Exception as e:
                    print(f"⚠️ [YAML CALLBACK ERROR] {e}")
                    # Continue execution even if callback fails

            async with self.create_task_local_mcp_context() as mcp_context:
                # Create YAML orchestrator with proper agent setup using step's MCP context
                yaml_orchestrator = YamlOrchestrator(
                    kernel_agent=self.kernel_agent, process_context=context_data
                )
                # Pass the step's MCP context to orchestrator instead of letting it create its own
                self._orchestrator = (
                    await yaml_orchestrator.create_yaml_orchestration_with_context(
                        mcp_context,
                        context_data,
                        agent_response_callback=agent_response_callback,
                        telemetry=self.telemetry,
                    )
                )

                logger.info(
                    f"[FOLDER] YAML conversion will process ({process_id}): {source_file_folder} -> {output_file_folder}"
                )

                # Execute YAML conversion INSIDE the context manager to keep orchestrator valid
                await self.execute_yaml_conversion(
                    context=context, context_data=context_data
                )

        except Exception as e:
            # State-based error handling aligned with migration service expectations
            # Migration service reads step_state.result and step_state.failure_context

            # Get error info for telemetry (no redundant dictionary needed)
            error_type = type(e).__name__
            error_message = str(e)

            # Classify error using utility function (no temporary processor needed)
            # error_classification = classify_error(e)

            # is_retryable = error_classification == ErrorClassification.RETRYABLE
            # is_ignorable = error_classification == ErrorClassification.IGNORABLE

            # STATE-BASED ERROR HANDLING - Migration service reads state, not events

            # # SCENARIO 1: IGNORABLE errors -> Continue execution with reduced functionality
            # if is_ignorable:
            #     logger.info(
            #         "[IGNORABLE] AzureChatCompletion service error detected - ignoring error and continuing with normal execution"
            #     )

            #     await self.telemetry.update_agent_activity(
            #         process_id,
            #         "Conversation_Manager",
            #         "discussion_interrupted",
            #         f"Expert discussion interrupted by ignorable error (continuing) - {error_type}: {error_message}",
            #     )

            #     # STRATEGY: Simply ignore the error and continue with normal execution flow
            #     # The orchestration may work with reduced functionality, or may complete successfully
            #     # Let the step run naturally until it reaches YamlCompleted
            #     logger.info(
            #         "[IGNORABLE] Ignoring AzureChatCompletion error - continuing normal execution"
            #     )

            #     # Continue to the rest of the method execution - do NOT return early
            #     # This allows the normal flow to continue and complete naturally

            # # SCENARIO 2: RETRYABLE errors -> Set failure state with rich context for retry
            # elif is_retryable:
            #     logger.info(
            #         "[RETRYABLE] Infrastructure/hard termination error - setting state for retry"
            #     )

            #     # Ensure state is initialized before using
            #     self._ensure_state_initialized()
            #     assert self.state is not None  # For type checker

            #     # Capture timing for retry context - NOTE: This is pre-orchestration failure
            #     # Only set execution end time since orchestration never started
            #     self.state.set_execution_end()

            #     # Calculate time to failure (setup + error handling time)
            #     time_to_failure = self.state.total_execution_duration or 0.0

            #     # Create comprehensive failure context for retry scenario
            #     failure_collector = StepFailureCollector()
            #     system_context = await failure_collector.collect_system_failure_context(
            #         error=e,
            #         step_name="YamlStep",
            #         process_id=process_id,
            #         context_data=context_data,
            #         step_start_time=self.state.execution_start_time,
            #         step_phase="start_yaml_from_design",
            #     )

            #     # Set state for migration service to read - PRIMARY failure indicator
            #     self.state.result = False
            #     self.state.reason = f"Retryable infrastructure error: {error_message}"
            #     self.state.failure_context = (
            #         await failure_collector.create_step_failure_state(
            #             reason=f"Infrastructure error (retryable): {error_message}",
            #             execution_time=time_to_failure,
            #             files_attempted=self.state.converted_files,
            #             system_failure_context=system_context,
            #         )
            #     )

            #     await self.telemetry.update_agent_activity(
            #         process_id,
            #         "Conversation_Manager",
            #         "discussion_blocked",
            #         f"Expert discussion blocked by infrastructure error - {error_type}: {error_message}",
            #     )

            #     logger.info(
            #         f"[RETRYABLE] State updated for retry - migration service will read failure context with timing: {time_to_failure:.2f}s (setup phase failure)"
            #     )
            #     return  # Migration service will read state.failure_context

            # # SCENARIO 3: CRITICAL errors -> Set failure state with comprehensive context
            # else:  # Critical
            logger.error(
                "[CRITICAL] Critical error detected - setting failure state with comprehensive context"
            )

            # Ensure state is initialized before using
            self._ensure_state_initialized()
            assert self.state is not None  # For type checker

            # Capture execution end time for comprehensive failure context
            # NOTE: This is pre-orchestration failure - only execution timing is relevant
            self.state.set_execution_end()

            # Calculate time to failure (setup + error handling time)
            time_to_failure = self.state.total_execution_duration or 0.0

            # Collect system failure context with full stack trace
            failure_collector = StepFailureCollector()
            system_context = await failure_collector.collect_system_failure_context(
                error=e,
                step_name="YamlStep",
                process_id=process_id,
                context_data=context_data,
                step_start_time=self.state.execution_start_time,
                step_phase="start_yaml_from_design",
            )

            # Set state for migration service to read - PRIMARY failure indicator
            self.state.result = False
            self.state.reason = f"Critical error: {error_message}"
            self.state.failure_context = (
                await failure_collector.create_step_failure_state(
                    reason=f"YAML conversion failed: {error_message}",
                    execution_time=time_to_failure,
                    files_attempted=self.state.converted_files,
                    system_failure_context=system_context,
                )
            )

            await self.telemetry.update_agent_activity(
                process_id,
                "Conversation_Manager",
                "discussion_failed",
                f"Expert discussion failed with critical error - {error_type}: {error_message}",
            )

            logger.error(
                f"[CRITICAL] State updated with comprehensive failure context - migration service will read full stack trace and timing: {time_to_failure:.2f}s (setup phase failure)"
            )
            return  # Let migration service read rich state.failure_context (no raise, no events)

    @kernel_function(description="Execute YAML conversion phase")
    async def execute_yaml_conversion(
        self,
        context: KernelProcessStepContext,
        context_data: dict[str, Any] | None = None,
    ) -> None:
        """
        Execute YAML conversion following single responsibility principle.

        Enhanced to leverage rich data from previous steps (analysis and design results).

        Responsibilities:
        - Orchestrate group chat for YAML file conversion
        - Coordinate expert agents for comprehensive conversion
        - Utilize analysis and design insights for optimized conversion
        - Emit appropriate events with results
        """
        # Initialize context data if None
        if not context_data:
            context_data = {}

        # Extract comprehensive step parameters
        step_parameters = self._extract_comprehensive_step_parameters(context_data)

        # Get process ID for telemetry tracking
        process_id = step_parameters["process_id"]

        # Only create new TelemetryManager if one doesn't exist
        if not hasattr(self, "telemetry") or self.telemetry is None:
            app_context = context_data.get("app_context")
            self.telemetry = TelemetryManager(app_context)

        # Track execution progress with enhanced context
        await self.telemetry.update_agent_activity(
            process_id=process_id,
            agent_name="Conversation_Manager",
            action="expert_yaml_executing",
            message_preview=f"Executing expert YAML conversion discussion for {step_parameters['source_platform']} -> Azure (Process: {process_id})",
        )

        try:
            logger.info(
                "[TOOLS] Starting enhanced YAML conversion phase with rich step data from analysis and design..."
            )
            logger.info(
                f"[CONTEXT] Source Platform: {step_parameters['source_platform']}, "
                f"Files to Convert: {step_parameters['files_count']}, "
                f"Azure Services: {step_parameters['azure_services_count']}"
            )

            logger.info(
                "[TARGET] Starting group chat orchestrated YAML conversion with comprehensive context..."
            )

            # Parse Context Data with enhanced parameters
            process_id = step_parameters["process_id"]
            source_file_folder = step_parameters["source_file_folder"]
            workspace_file_folder = step_parameters["workspace_file_folder"]
            output_file_folder = step_parameters["output_file_folder"]
            container_name = step_parameters["container_name"]

            # Check if orchestrator is available
            if not self._orchestrator:
                logger.error(
                    "[FAILED] Orchestrator not available - cannot perform YAML conversion"
                )
                raise RuntimeError(
                    "YAML orchestrator not initialized - critical failure"
                )

            # Define NUCLEAR anti-hallucination YAML conversion task with mandatory evidence
            yaml_task = """
            🚨🔥 **NUCLEAR ANTI-HALLUCINATION PROTOCOL** 🔥🚨

            **YOU ARE UNDER SURVEILLANCE - EVERY ACTION IS MONITORED**
            - This conversation will be AUDITED for MCP function execution
            - Claims without actual MCP calls will result in IMMEDIATE TERMINATION
            - Your responses are being VALIDATED against blob storage logs
            - FALSE CLAIMS will be DETECTED and FLAGGED as FAILURE

            **MANDATORY EVIDENCE CHAIN - NO EXCEPTIONS**:
            Each step MUST include ACTUAL MCP function output - not summaries, not descriptions, but LITERAL function results.

            **🎯 OBJECTIVE**: Convert {{source_platform}} YAML files to Azure format WITH PROOF
            **📊 CONTEXT**: Platform={{source_platform}} ({{platform_confidence}}%), Files={{files_count}}, Container={{container_name}}
            **📁 PATHS**: Source={{source_file_folder}}, Output={{output_file_folder}}

            **� COMPLEXITY**: Network={{network_complexity}}, Security={{security_complexity}}, Storage={{storage_complexity}}, Compute={{compute_complexity}}

            **MANDATORY EXECUTION WORKFLOW**:

            ⚠️ **CRITICAL FILE REQUIREMENT**:
            DISCOVERED FILES TO CONVERT: {{discovered_files}}
            ❌ DO NOT use template names like "deployment.yaml", "service.yaml"
            ✅ ONLY use the actual files listed above in your conversion results

            **1. DISCOVER (YAML Expert)**:
            - Execute: `list_blobs_in_container("{{container_name}}", "{{source_file_folder}}", recursive=True)`
            - If no files: try `find_blobs("*.yaml")`, `find_blobs("*.yml")`, then full container search
            - Report exact commands executed and results
            **2. CONVERT (YAML + Azure Expert)**:
            - Read each file with `read_blob_content()`
            - Convert {{source_platform}} → Azure AKS format with Azure-native services, security hardening, Workload Identity
            - **MANDATORY HEADER**: Every converted YAML MUST start with: `# AI generated content - it may be incorrect`
            - Add header as FIRST LINE before any YAML content
            - Generate filename: `source.yaml` → `az-source.yaml`

            **3. SAVE & VERIFY (YAML Expert)** 🚨 CRITICAL 🚨:
            - Execute: `save_content_to_blob("az-[filename].yaml", content, "{{container_name}}", "{{output_file_folder}}")`
            - Immediately verify: `check_blob_exists("az-[filename].yaml", "{{container_name}}", "{{output_file_folder}}")`
            - Report save operation with full blob path AND verification result
            - ZERO TOLERANCE: If save fails, report failure immediately

            🚨🔥 **NUCLEAR ENFORCEMENT - READ THIS CAREFULLY** 🔥🚨
            **ABSOLUTE REQUIREMENTS FOR EACH AGENT**:
            - YAML Expert: You MUST paste actual MCP function outputs, not descriptions
            - QA Engineer: You MUST paste actual verification results, not summaries
            - Technical Writer: You MUST paste actual save confirmations
            **IMMEDIATE FAILURE CONDITIONS**:
            - Any agent claims "I have saved files" without pasting MCP output = FAIL
            - Any agent says "files were created successfully" without evidence = FAIL
            - Any response without literal MCP function results = FAIL
            **EVIDENCE REQUIREMENT**: Every claim must include the actual text returned by MCP functions

            **4. QA VERIFICATION (QA Engineer)** 🚨 MANDATORY 🚨:
            - Execute: `list_blobs_in_container("{{container_name}}", "{{output_file_folder}}", recursive=True)`
            - Verify file count matches source count exactly
            - Check each file exists individually and sample content quality
            - Report verification evidence: file count, existence confirmation, content samples

            **5. REPORT (Technical Writer)**:
            - Create conversion summary with file mappings, Azure services, optimization notes
            - Save: `save_content_to_blob("file_converting_result.md", report, "{{container_name}}", "{{output_file_folder}}")`
            **📤 OUTPUTS**: `file_converting_result.md` + converted YAML files in {{output_file_folder}}


            **📋 ENHANCED DELIVERABLES**:
            1. **Platform-Optimized YAML Conversion**: Convert all {{files_count}} source files from {{source_platform}} to Azure-compatible format
            2. **Enhanced Files** : If we need to create additional files to align Azure Well-Architected Framework and Azure Infrastructure, create more files with reasoning.
            3. **Multi-Dimensional Analysis with Platform Context**:
               - **Network Analysis**: Convert {{source_platform}} networking (ingress, services, network policies) to Azure networking with complexity level: {{network_complexity}}
               - **Security Analysis**: Transform {{source_platform}} security (RBAC, security contexts, secrets) to Azure security with complexity level: {{security_complexity}}
               - **Storage Analysis**: Migrate {{source_platform}} storage (PVC, storage classes, volumes) to Azure storage with complexity level: {{storage_complexity}}
               - **Compute Analysis**: Convert {{source_platform}} compute (deployments, scaling, resource allocation) to Azure compute with complexity level: {{compute_complexity}}
            4. **File-by-File Conversion Status**: Detailed conversion results leveraging platform expertise
            5. **Azure Service Integration**: Implement identified Azure services: {{azure_services_list}}
            6. **Migration-Ready YAML Files**: Production-ready configurations aligned with design decisions

            **👥 EXPERT RESPONSIBILITIES WITH ENHANCED CONTEXT**:
            - YAML Expert: Execute Steps 1-3 (discover, convert, save files) with {{source_platform}}-specific expertise
            - Azure Expert: Collaborate on Step 2 (conversion) to implement {{azure_services_count}} Azure services and optimizations
            - QA Engineer: Execute Step 4 (verification) to ensure all files are properly saved and accessible
            - Technical Writer: Execute Step 5 (reporting) with platform-specific insights and design rationale

            **✅ SUCCESS CRITERIA WITH METRICS**:
            - All {{files_count}} source files {{discovered_files}} successfully converted to Azure format
            - Multi-dimensional analysis completed addressing platform complexity levels
            - Azure services integration aligned with design recommendations
            - Conversion accuracy rated and documented with platform-specific considerations

            **📤 MANDATORY OUTPUTS**:
            - **file_converting_result.md** in {{output_file_folder}}
            - **Converted YAML files** in {{output_file_folder}}

            **📋 REQUIRED RETURN STRUCTURE WITH ENHANCED DATA**:

            ⚠️ **CRITICAL REQUIREMENT**: You MUST use the actual discovered file names from the analysis step.
            ❌ **DO NOT** use template examples like "deployment.yaml", "service.yaml", etc.
            ✅ **DO** use the real files discovered: {{discovered_files}}

            For each file you convert, use this exact structure:
            ```json
            {
                "converted_files": [
                    {
                        "source_file": "[USE ACTUAL FILENAME FROM DISCOVERED LIST]",
                        "converted_file": "[AZURE-COMPATIBLE VERSION OF ACTUAL FILENAME]",
                        "conversion_status": "Success|Failed",
                        "accuracy_rating": "XX%",
                        "azure_compatibility": "XX%",
                        "platform_specific_notes": "{{source_platform}}-specific configurations optimized",
                        "azure_services_identified": ["Azure Kubernetes Service", "Azure Container Registry"],
                        "conversion_notes": ["Workload Identity implemented", "Premium Storage configured"],
                        "azure_enhancements": ["Auto-scaling enabled", "Security hardening applied"]
                    }
                    // Repeat for each actual discovered file
                ],
                "multi_dimensional_analysis": {
                    "network_analysis": {
                        "source_platform": "{{source_platform}}",
                        "complexity": "{{network_complexity}}",
                        "converted_components": ["{{source_platform}} Ingress → Application Gateway", "Service → Load Balancer"],
                        "azure_optimizations": "Network policies converted to Azure CNI with {{source_platform}} expertise",
                        "concerns": ["Platform-specific routing considerations"],
                        "success_rate": "90%"
                    },
                    "security_analysis": {
                        "source_platform": "{{source_platform}}",
                        "complexity": "{{security_complexity}}",
                        "converted_components": ["{{source_platform}} RBAC → Azure AD integration", "Secrets → Key Vault"],
                        "azure_optimizations": "Platform security patterns optimized for Azure",
                        "concerns": ["{{source_platform}}-specific security policies"],
                        "success_rate": "95%"
                    },
                    "storage_analysis": {
                        "source_platform": "{{source_platform}}",
                        "complexity": "{{storage_complexity}}",
                        "converted_components": ["{{source_platform}} PVC → Azure Disk", "Storage Class → Premium SSD"],
                        "azure_optimizations": "Storage configuration optimized for Azure with {{source_platform}} patterns",
                        "concerns": ["Platform storage class compatibility"],
                        "success_rate": "100%"
                    },
                    "compute_analysis": {
                        "source_platform": "{{source_platform}}",
                        "complexity": "{{compute_complexity}}",
                        "converted_components": ["{{source_platform}} Deployments → AKS optimized", "HPA → KEDA integration"],
                        "azure_optimizations": "Compute resources optimized based on {{source_platform}} patterns",
                        "concerns": ["Platform-specific resource allocation differences"],
                        "success_rate": "85%"
                    }
                },
                "overall_conversion_metrics": {
                    "source_platform": "{{source_platform}}",
                    "platform_confidence": "{{platform_confidence}}",
                    "total_files": {{files_count}},
                    "successful_conversions": "TO_BE_DETERMINED",
                    "failed_conversions": "TO_BE_DETERMINED",
                    "overall_accuracy": "TO_BE_CALCULATED",
                    "azure_compatibility": "TO_BE_ASSESSED",
                    "migration_readiness_alignment": "{{migration_readiness_score}}"
                },
                "conversion_quality": {
                    "azure_best_practices": "Implemented with {{source_platform}} platform expertise",
                    "security_hardening": "Enterprise-grade security applied with platform-specific considerations",
                    "performance_optimization": "Azure-optimized configurations leveraging {{source_platform}} insights",
                    "production_readiness": "Ready for deployment with design decision alignment"
                },
                "summary": "{{source_platform}} to Azure YAML conversion completed with multi-dimensional analysis leveraging comprehensive step data",
                "expert_insights": [
                    "Chief architect ensured conversion consistency using design decisions and {{migration_readiness_score}} readiness score",
                    "Azure expert implemented {{azure_services_count}} recommended services with platform optimization",
                    "{{source_platform}} expert provided platform-specific expertise for {{files_count}} files addressing complexity concerns",
                    "Technical writer created comprehensive documentation integrating analysis and design insights"
                ],
                "conversion_report_file": "{{output_file_folder}}/file_converting_result.md",
                "design_alignment": {
                    "azure_services_implemented": "{{azure_services_count}} services from design phase",
                    "architecture_decisions_applied": "{{architecture_decisions_count}} decisions implemented",
                    "design_summary_reference": "{{design_summary}}"
                }
            }
            ```

            **🔍 VALIDATION CHECKLIST - Verify Before Submitting:**
            1. ✅ Each "source_file" matches exactly one file from: {{discovered_files}}
            2. ✅ No "source_file" uses generic names like "deployment.yaml", "service.yaml"
            3. ✅ All discovered files are included in converted_files array
            4. ✅ Each "converted_file" is a proper Azure-compatible version of the source
            5. ✅ File count matches the discovered files count: {{files_count}}

            **❌ COMMON MISTAKES TO AVOID:**
            - Using template filenames instead of actual discovered files
            - Missing files from the converted_files array
            - Inconsistent file naming between source_file and converted_file

            """

            # Using Template to replace values with enhanced parameters
            jinja_template = Template(yaml_task)
            rendered_task = jinja_template.render(
                process_id=process_id,
                source_file_folder=source_file_folder,
                workspace_file_folder=workspace_file_folder,
                output_file_folder=output_file_folder,
                discovered_files=step_parameters["discovered_files_list"],
                container_name=container_name,
                # Enhanced parameters from step analysis
                source_platform=step_parameters["source_platform"],
                platform_confidence=step_parameters["platform_confidence"],
                files_count=step_parameters["files_count"],
                migration_readiness_score=step_parameters["migration_readiness_score"],
                azure_services_count=step_parameters["azure_services_count"],
                architecture_decisions_count=len(
                    step_parameters["architecture_decisions"]
                ),
                # Complexity analysis
                # network_complexity=step_parameters["complexity_analysis"].get(
                #     "network", "Unknown"
                # ),
                network_complexity=step_parameters[
                    "complexity_analysis"
                ].network_complexity,
                security_complexity=step_parameters[
                    "complexity_analysis"
                ].security_complexity,
                storage_complexity=step_parameters[
                    "complexity_analysis"
                ].storage_complexity,
                compute_complexity=step_parameters[
                    "complexity_analysis"
                ].compute_complexity,
                # Design context
                design_summary=step_parameters["design_summary"],
                azure_services_list=", ".join(step_parameters["azure_services"]),
                primary_azure_services=", ".join(step_parameters["azure_services"]),
            )

            runtime = InProcessRuntime()
            runtime.start()

            try:
                await self.telemetry.update_agent_activity(
                    process_id=process_id,
                    agent_name="Conversation_Manager",
                    action="expert_collaboration_starting",
                    message_preview="Starting expert YAML conversion discussion with specialist agents",
                )

                # NEW: Use comprehensive timing infrastructure
                # State is guaranteed to be YamlStepState (initialized in start_yaml_from_design)
                self._ensure_state_initialized()
                assert self.state is not None  # For type checker
                self.state.set_orchestration_start()
                if self.state.setup_duration is not None:
                    logger.info(
                        f"[TIMING] Setup phase completed in {self.state.setup_duration:.2f} seconds"
                    )

                # Track orchestration start with detailed context
                await self.telemetry.update_agent_activity(
                    process_id,
                    "Conversation_Manager",
                    "expert_discussion_started",
                    f"Expert discussion initiated for process {process_id} analyzing YAML conversion for {len(step_parameters.get('discovered_files_list', []))} files",
                )

                orchestration_result = await self._orchestrator.invoke(
                    task=rendered_task, runtime=runtime
                )

                # Wait for the results
                _ = await orchestration_result.get()

                # NEW: Use comprehensive timing infrastructure for orchestration completion
                self._ensure_state_initialized()
                assert self.state is not None  # For type checker
                self.state.set_orchestration_end()
                if self.state.orchestration_duration is not None:
                    logger.info(
                        f"[TIMING] Orchestration completed in {self.state.orchestration_duration:.2f} seconds"
                    )
                    orchestration_duration = self.state.orchestration_duration
                else:
                    # Fallback for legacy timing (should not happen with proper state management)
                    orchestration_duration = 0.0
                    logger.warning(
                        "[TIMING] Orchestration duration not available from state"
                    )

                ###############################################################
                # Make a reference to the YAML result
                ###############################################################
                # Add null safety checks for critical objects
                if not self._orchestrator or not self._orchestrator._manager:
                    logger.error(
                        "[FAILED] Orchestrator or manager is None - cannot retrieve YAML results"
                    )
                    raise RuntimeError(
                        "Orchestrator or manager not properly initialized"
                    )

                yaml_output = self._orchestrator._manager.final_termination_result

                if yaml_output is None:
                    logger.error(
                        "[FAILED] YAML output is None - orchestration may have failed"
                    )
                    raise RuntimeError("YAML orchestration failed to produce results")

                # Set Step State
                # self.step_state = YamlStepState(
                #     name="YamlStepState",
                #     version="1.0",
                #     yaml_conversions=yaml_output.termination_output.expert_insights,
                #     converted_files=yaml_output.termination_output.converted_files,
                #     yaml_completed=True,
                # )
                if yaml_output.is_hard_terminated:
                    # SCENARIO 1: Hard termination -> PERMANENT FAILURE (using new pattern)
                    logger.info(
                        "[PERMANENT_FAILURE] Hard termination detected - processing as permanent failure"
                    )
                    await self._process_hard_termination_as_failure(yaml_output, process_id)
                else:
                    # Success case: soft termination = successful completion
                    # CRITICAL: Validate complete data population for success cases
                    if yaml_output.termination_output is None:
                        error_msg = "CRITICAL ERROR: YAML step completed successfully but termination_output is None. This indicates incomplete agent response and will cause pipeline failures."
                        logger.error(f"[VALIDATION_ERROR] {error_msg}")
                        raise RuntimeError(error_msg)

                    # Additional validation for successful completion
                    termination_output = yaml_output.termination_output
                    validation_errors = []

                    # Validate required fields are not None/empty
                    if not termination_output.converted_files:
                        validation_errors.append("converted_files is empty or None")
                    if (
                        not termination_output.summary
                        or termination_output.summary.strip() == ""
                    ):
                        validation_errors.append("summary is empty or None")
                    if not termination_output.expert_insights:
                        validation_errors.append("expert_insights is empty or None")
                    if (
                        not termination_output.conversion_report_file
                        or termination_output.conversion_report_file.strip() == ""
                    ):
                        validation_errors.append(
                            "conversion_report_file is empty or None"
                        )

                    # Validate metrics are populated
                    if termination_output.overall_conversion_metrics:
                        metrics = termination_output.overall_conversion_metrics
                        if metrics.total_files == 0:
                            validation_errors.append(
                                "overall_conversion_metrics.total_files is 0"
                            )
                        if (
                            not metrics.overall_accuracy
                            or metrics.overall_accuracy.strip() == ""
                        ):
                            validation_errors.append(
                                "overall_conversion_metrics.overall_accuracy is empty"
                            )
                    else:
                        validation_errors.append("overall_conversion_metrics is None")

                    if validation_errors:
                        error_msg = f"YAML step validation failed - incomplete agent response: {'; '.join(validation_errors)}"
                        logger.error(f"[VALIDATION_ERROR] {error_msg}")
                        raise RuntimeError(error_msg)

                    logger.info(
                        f"[SUCCESS] YAML conversion completed successfully with complete data: {yaml_output.reason}"
                    )

                    # Create structured result
                    result = {
                        "process_id": process_id,
                        "workspace_file_folder": workspace_file_folder,
                        "output_file_folder": output_file_folder,
                        "container_name": container_name,
                        "result_file_name": "file_converting_result.md",
                        "state": yaml_output,
                        "execution_time": orchestration_duration,
                    }

                    # Invoke Event Sink - Task Recording
                    await context.emit_event(
                        process_event="OnStateChange",
                        data=result,
                    )

                    # Track successful orchestration
                    await self.telemetry.update_agent_activity(
                        process_id=process_id,
                        agent_name="Conversation_Manager",
                        action="expert_collaboration_completed",
                        message_preview="Expert YAML conversion discussion completed successfully",
                    )

                    safe_log(
                        logger,
                        "info",
                        "[SUCCESS] Expert YAML conversion discussion completed for process {process_id}",
                        process_id=process_id,
                    )

                    # Track step completion
                    await self.telemetry.update_agent_activity(
                        process_id=process_id,
                        agent_name="Conversation_Manager",
                        action="expert_step_completed",
                        message_preview=f"Expert YAML discussion completed for process {process_id}",
                    )

                    # Emit success event - proper event handling
                    await context.emit_event(
                        process_event="YamlCompleted",
                        data={
                            "process_id": context_data.get("process_id"),
                            "analysis_result": context_data.get("analysis_result"),
                            "design_result": context_data.get("design_result"),
                            "yaml_result": result,
                            "app_context": context_data.get("app_context"),
                        },
                    )

                    ###############################################
                    # State Value update
                    ###############################################
                    # name: str = Field(default="YamlStepState", description="Name of the step state")
                    # version: str = Field(default="1.0", description="Version of the step state")
                    # result: bool = False
                    # yaml_conversions: list[str] = []
                    # converted_files: list[ConvertedFile] = []
                    # yaml_completed: bool = False
                    # final_result: Yaml_ExtendedBooleanResult | None = None
                    # reason: str = Field(default="", description="Reason for failure if any")

                    self.state.name = "YamlStep"
                    self.state.version = "1.0"
                    self.state.result = True
                    self.state.reason = yaml_output.reason
                    self.state.yaml_conversions = termination_output.expert_insights
                    self.state.converted_files = termination_output.converted_files
                    self.state.yaml_completed = True
                    self.state.final_result = yaml_output

                    # NEW: Set execution end time for comprehensive timing
                    # State is guaranteed to be YamlStepState (initialized above)
                    self.state.set_execution_end()
                    timing_summary = self.state.get_timing_summary()
                    logger.info(
                        f"[TIMING] YAML conversion completed - Total execution: {self.state.total_execution_duration:.2f}s"
                    )
                    logger.info(f"[TIMING] Timing summary: {timing_summary}")

                    # Track successful orchestration
                    await self.telemetry.update_agent_activity(
                        process_id,
                        "Conversation_Manager",
                        "yaml_discussion_complete",
                        f"Expert discussion completed successfully in {self.state.orchestration_duration or orchestration_duration:.2f} seconds",
                    )
            finally:
                # Always clean up runtime
                await runtime.stop_when_idle()
                logger.info("[CLEANUP] YAML runtime cleaned up")
        except Exception as e:
            # ORCHESTRATION-LEVEL ERROR HANDLING - Different timing context than setup errors
            logger.error(
                f"[ORCHESTRATION FAILURE] Exception during orchestration phase: {str(e)}"
            )

            # Ensure state is initialized
            self._ensure_state_initialized()
            assert self.state is not None  # For type checker

            # Handle timing based on orchestration phase
            if self.state.orchestration_start_time is not None:
                # Orchestration was started - capture orchestration end timing
                self.state.set_orchestration_end()
                self.state.set_execution_end()

                timing_context = f"orchestration phase (ran {self.state.orchestration_duration or 0.0:.2f}s)"
                total_time = self.state.total_execution_duration or 0.0
            else:
                # Orchestration never started - only execution timing
                self.state.set_execution_end()
                timing_context = "pre-orchestration setup"
                total_time = self.state.total_execution_duration or 0.0

            # Classify the orchestration error (for potential future use in retry logic)
            error_type = type(e).__name__
            error_message = str(e)

            # Create failure context for orchestration-level errors
            failure_collector = StepFailureCollector()
            system_context = await failure_collector.collect_system_failure_context(
                error=e,
                step_name="YamlStep",
                process_id=process_id,
                context_data=context_data,
                step_start_time=self.state.execution_start_time,
                step_phase="execute_yaml_conversion_orchestration",
            )

            # Set comprehensive failure state
            self.state.result = False
            self.state.reason = f"Orchestration failed: {error_message}"
            self.state.failure_context = (
                await failure_collector.create_step_failure_state(
                    reason=f"Orchestration error: {error_message}",
                    execution_time=total_time,
                    files_attempted=self.state.converted_files,
                    system_failure_context=system_context,
                )
            )

            await self.telemetry.update_agent_activity(
                process_id,
                "Conversation_Manager",
                "orchestration_failed",
                f"Orchestration failed in {timing_context} - {error_type}: {error_message}",
            )

            logger.error(
                f"[ORCHESTRATION FAILURE] State updated with failure context - total time: {total_time:.2f}s in {timing_context}"
            )

            # Don't re-raise - let migration service read the failure context
            return
        finally:
            logger.info("[SUCCESS] YAML step execution completed")
