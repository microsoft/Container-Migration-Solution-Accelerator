"""
Analysis Step - Single responsibility: Auto-discover YAML files and detect platform.

Following SK Process Framework best practices:
- Single responsibility principle
- Proper event handling with error management
- Isolated kernel instance
- Clear input/output via events
- Step-specific group chat orchestration
"""

import asyncio
import time
from typing import TYPE_CHECKING, Any

from jinja2 import Template
from pydantic import BaseModel, Field, ValidationError
from semantic_kernel.agents import GroupChatOrchestration

# Run the orchestration with the rendered task
from semantic_kernel.agents.runtime import InProcessRuntime
from semantic_kernel.functions import kernel_function
from semantic_kernel.processes.kernel_process import (
    KernelProcessStep,
    KernelProcessStepContext,
    KernelProcessStepState,
)

if TYPE_CHECKING:
    from libs.models.failure_context import StepFailureState

from libs.application.application_context import AppContext
from libs.base.KernelAgent import semantic_kernel_agent
from libs.steps.orchestration.analysis_orchestration import (
    AnalysisOrchestrator,
)
from libs.steps.step_failure_collector import StepFailureCollector
from plugins.mcp_server import MCPBlobIOPlugin, MCPDatetimePlugin, MCPMicrosoftDocs
from utils.agent_telemetry import TelemetryManager
from utils.logging_utils import create_migration_logger, safe_log
from utils.mcp_context import PluginContext, with_name
from utils.tool_tracking import ToolTrackingMixin

from .base_step_state import BaseStepState
from .orchestration.models.analysis_result import Analysis_ExtendedBooleanResult

logger = create_migration_logger(__name__)


# class AnalysisStepState(KernelBaseModel):
#     """State for the Analysis step following best practices."""

#     platform_detected: str = ""
#     files_discovered: list = []
#     analysis_completed: bool = False
#     final_result: dict[str, Any] | None = (
#         None  # Store complete result for main.py access
#     )


class AnalysisStepState(BaseStepState):
    """State for the Analysis step following best practices."""

    # Base fields required by KernelProcessStepState
    name: str = Field(default="AnalysisStepState", description="Name of the step state")
    version: str = Field(default="1.0", description="Version of the step state")

    result: bool | None = None  # None = not started, True = success, False = failed
    reason: str = ""
    platform_detected: str = ""
    files_discovered: list = []
    analysis_completed: bool = False
    final_result: Analysis_ExtendedBooleanResult | None = None

    requires_immediate_retry: bool = Field(default=False)
    termination_details: dict[str, Any] | None = Field(default=None)


class analysis_parameter(BaseModel):
    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}

    process_id: str
    source_file_folder: str
    workspace_file_folder: str
    output_file_folder: str
    container_name: str
    app_context: AppContext


class AnalysisStep(KernelProcessStep[AnalysisStepState], ToolTrackingMixin):
    """
    Analysis step that discovers YAML files and detects source platform.

    Following SK Process Framework best practices:
    - Single responsibility: file discovery and platform detection only
    - Isolated kernel instance to prevent recursive invocation
    - Proper error handling and event emission
    - Simple, focused functionality
    """

    state: AnalysisStepState | None = Field(
        default_factory=lambda: AnalysisStepState(
            name="AnalysisStepState", version="1.0"
        )
    )

    # For Pydantic model validation
    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}

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
        # Filter out known problematic kwargs that aren't needed by KernelProcessStep
        super().__init__()
        logger.info(
            "[Initiation] ANALYSIS STEP CONSTRUCTOR: Synchronous initialization complete"
        )

        self.kernel_agent = None
        self._orchestrator: GroupChatOrchestration | None = None

    async def activate(self, state: KernelProcessStepState[AnalysisStepState]):
        """
        Activate the step for state initialization only.

        Note: Kernel agent creation moved to start_migration_analysis() for lazy initialization.
        This avoids unnecessary resource allocation for steps that may never execute.
        """
        self.state = state.state
        # Ensure state is never None
        self._ensure_state_initialized()

    def _ensure_state_initialized(self) -> None:
        """Ensure state is properly initialized before use."""
        if self.state is None:
            self.state = AnalysisStepState(name="AnalysisStepState", version="1.0")

    def _create_analysis_parameters(
        self, context_data: dict[str, Any]
    ) -> tuple[bool, analysis_parameter | None]:
        """
        Create and validate analysis parameters using Pydantic model validation.

        This method provides comprehensive parameter validation using Pydantic's built-in
        validation capabilities, eliminating the need for a separate ParameterValidator.

        Returns:
            tuple[bool, analysis_parameter | None]: (is_valid, validated_parameters)
        """
        try:
            # Use Pydantic's model_validate for comprehensive type checking and validation
            validated_params = analysis_parameter.model_validate(context_data)
            return True, validated_params

        except ValidationError as e:
            # Enhanced error logging with detailed Pydantic validation errors
            error_details = []
            for error in e.errors():
                field = (
                    error.get("loc", ["unknown"])[0] if error.get("loc") else "unknown"
                )
                message = error.get("msg", "Validation failed")
                error_details.append(f"{field}: {message}")

            logger.error(f"Parameter validation failed: {'; '.join(error_details)}")
            logger.error(f"Full validation error: {e}")

            return False, None

        except Exception as e:
            # Handle any other unexpected errors during validation
            logger.error(f"Unexpected error during parameter validation: {e}")
            return False, None

    def _create_termination_context_data(self, analysis_output) -> dict[str, Any]:
        """Create context data for termination failure scenarios"""
        context_data = {
            "termination_type": analysis_output.termination_type,
            "termination_reason": analysis_output.reason,
            "blocking_issues": list(analysis_output.blocking_issues)
            if analysis_output.blocking_issues
            else [],
        }

        # Add termination output details if available
        if analysis_output.termination_output:
            context_data.update(
                {
                    "platform_detected": analysis_output.termination_output.platform_detected,
                    "confidence_score": analysis_output.termination_output.confidence_score,
                    "files_discovered": analysis_output.termination_output.files_discovered
                    or [],
                    "expert_insights": analysis_output.termination_output.expert_insights
                    or [],
                }
            )

        return context_data

    async def _process_hard_termination_as_failure(
        self, analysis_output, process_id: str
    ) -> None:
        """Process ALL hard terminations as permanent failures using existing error infrastructure"""
        # Extract discovered files safely
        discovered_files = []
        if analysis_output.termination_output and hasattr(
            analysis_output.termination_output, "files_discovered"
        ):
            discovered_files = analysis_output.termination_output.files_discovered or []

        # Step 1: Update telemetry with failure notification
        await self.telemetry.update_agent_activity(
            process_id,
            "Conversation_Manager",
            "analysis_permanently_failed",
            f"Analysis failed permanently due to {analysis_output.termination_type}: {analysis_output.reason}. Expert consensus: {analysis_output.blocking_issues}",
        )

        # Step 2: Create failure context using existing StepFailureCollector
        # Create "virtual exception" for termination scenario
        termination_error = ValueError(
            f"Hard termination: {analysis_output.termination_type} - {analysis_output.reason}"
        )

        # Use existing StepFailureCollector
        failure_collector = StepFailureCollector()
        system_context = await failure_collector.collect_system_failure_context(
            error=termination_error,
            step_name="AnalysisStep",
            process_id=process_id,
            context_data=self._create_termination_context_data(analysis_output),
            step_start_time=self.state.execution_start_time,
            step_phase="hard_termination_analysis",
        )

        # Step 3: Set failure state (NOT retry state)
        self._ensure_state_initialized()
        assert self.state is not None  # For type checker

        # Set up basic state (similar to current logic but as FAILURE)
        self.state.name = "AnalysisStepState"
        self.state.id = "Analysis"
        self.state.version = "1.0"
        self.state.result = False  # FAILURE, not retry
        self.state.analysis_completed = False
        self.state.files_discovered = discovered_files
        self.state.platform_detected = (
            analysis_output.termination_output.platform_detected
            if analysis_output.termination_output
            and hasattr(analysis_output.termination_output, "platform_detected")
            else "Unknown"
        )
        self.state.final_result = analysis_output
        self.state.reason = f"Hard termination: {analysis_output.termination_type} - {analysis_output.reason}"

        # Set failure context using existing infrastructure
        self.state.failure_context = await failure_collector.create_step_failure_state(
            reason=f"Analysis terminated: {analysis_output.termination_type} - {analysis_output.reason}",
            execution_time=self.state.total_execution_duration or 0.0,
            files_attempted=discovered_files,
            system_failure_context=system_context,
        )

        # CRITICAL: Do NOT set retry flags
        # self.state.requires_immediate_retry = False (default)
        # No termination_details for retry

        # Step 4: Record failure outcome in telemetry
        failure_details = {
            "termination_type": analysis_output.termination_type,
            "termination_reason": analysis_output.reason,
            "blocking_issues": list(analysis_output.blocking_issues)
            if analysis_output.blocking_issues
            else [],
            "expert_analysis": analysis_output.termination_output.model_dump()
            if analysis_output.termination_output
            else None,
            "files_discovered": discovered_files,
            "platform_detected": (
                analysis_output.termination_output.platform_detected
                if analysis_output.termination_output
                and hasattr(analysis_output.termination_output, "platform_detected")
                else None
            ),
            "is_permanent_failure": True,
            "retry_recommended": False,
        }

        # Record in telemetry using existing infrastructure
        await self.telemetry.record_failure_outcome(
            process_id=process_id,
            error_message=f"Hard termination: {analysis_output.termination_type} - {analysis_output.reason}",
            failed_step="AnalysisStep",
            failure_details=failure_details,
        )

        logger.info(
            f"[PERMANENT_FAILURE] Hard termination processed as permanent failure: {analysis_output.termination_type} - "
            f"Migration service will generate failure report (no retry)"
        )

    @kernel_function(
        description="Handle initial migration start event with comprehensive validation"
    )
    async def start_migration_analysis(
        self, context: KernelProcessStepContext, context_data: dict[str, Any]
    ) -> None:
        """
        Handle the initial StartMigration event with comprehensive parameter validation.

        This function performs complete parameter validation using Pydantic models
        before delegating to execute_analysis. Each step creates its own PluginContext
        for clean isolation.

        Uses simplified state-based failure handling instead of complex event routing.
        """
        self._ensure_state_initialized()

        # State is guaranteed to be AnalysisStepState after _ensure_state_initialized()
        if self.state:
            # Initialize comprehensive timing infrastructure
            self.state.set_execution_start()

        is_valid, parameters = self._create_analysis_parameters(context_data)
        process_id = context_data.get("process_id")  # type: ignore

        if not is_valid:
            # NEW: Enhanced parameter validation failure with comprehensive timing context
            logger.error(
                "[FAILED] Parameter validation failed - collecting failure context"
            )

            # Capture execution end time for parameter validation failure
            # State is guaranteed to be AnalysisStepState (validated at method start)
            if self.state:
                self.state.set_execution_end()

                # Collect comprehensive failure context for parameter validation failure
                failure_collector = StepFailureCollector()

                # Create a simple validation error for failure context
                validation_error = ValueError(
                    "Parameter validation failed - required fields missing or invalid"
                )

                system_context = await failure_collector.collect_system_failure_context(
                    error=validation_error,
                    step_name="AnalysisStep",
                    process_id=process_id,
                    context_data=context_data,
                    step_start_time=self.state.execution_start_time,
                    step_phase="parameter_validation",
                )

                # Create complete step failure state for parameter validation
                self.state.failure_context = await failure_collector.create_step_failure_state(
                    reason="Parameter validation failed - required fields missing or invalid",
                    execution_time=self.state.total_execution_duration or 0.0,
                    files_attempted=[],  # No files attempted during parameter validation
                    system_failure_context=system_context,
                )

                logger.error(
                    f"Parameter validation failed with timing context: {self.state.get_timing_summary()}"
                )

                # Instead of emitting events, we now have rich failure context in state
                # The migration service can check state.failure_context for detailed error information
                logger.error(
                    "[FAILED] Parameter validation failed - failure context collected in state"
                )
            return

        #####################################################
        # ok, no problem go a head to take analysis
        #####################################################
        if parameters:
            # process_id: str = context_data.get("process_id", "not_passed")
            process_id: str = parameters.process_id
            # Create Telemetry
            self.telemetry = TelemetryManager(parameters.app_context)

        if self.kernel_agent is None:
            logger.info("[TOOLS] ANALYSIS STEP: Creating kernel agent for execution...")
            ################################################
            # Create and setup Kernel
            ###############################################
            self.kernel_agent = semantic_kernel_agent(
                env_file_path=None,  # Do not load .env file
                custom_service_prefixes=None,
                use_entra_id=True,
            )
            logger.info("[TOOLS] ANALYSIS STEP: About to initialize kernel agent...")
            ###########################################
            # Initialize Kernel
            ###########################################
            await self.kernel_agent.initialize_async()
            logger.info("[SUCCESS] ANALYSIS STEP: Kernel agent ready for execution")

        logger.info(
            "[SUCCESS] ANALYSIS STEP ACTIVATE: Step state initialized (kernel agent will be created when needed)"
        )

        ##################################################
        # Step Transition
        ##################################################
        await self.telemetry.transition_to_phase(
            process_id=process_id, phase="Analysis", step="Analysis"
        )
        try:
            logger.info(
                "[START] Received StartMigration event, starting analysis with lazy kernel agent initialization..."
            )

            # Initialize step-level telemetry - moved here as this is when step actually starts
            await self.telemetry.update_agent_activity(
                process_id=process_id,
                agent_name="Conversation_Manager",
                action="analysis_starting",
                message_preview=f"Starting expert discussion for platform analysis (process {process_id})",
            )
            await self.telemetry.update_agent_activity(
                process_id=process_id,
                agent_name="Conversation_Manager",
                action="expert_coordination_starting",
                message_preview="Coordinating platform experts for file discovery and analysis",
            )

            # Use validated parameters for processing
            if parameters:
                source_file_folder = parameters.source_file_folder
                output_file_folder = parameters.output_file_folder

            async def agent_response_callback(message):
                try:
                    agent_name = getattr(message, "name", "Unknown_Agent")
                    content = getattr(message, "content", "No content")

                    print(f"📝 [ANALYSIS CALLBACK] Agent: {agent_name}")
                    print(f"📝 [ANALYSIS CALLBACK] Content: {content[:200]}...")

                    # Enhanced tool usage detection and tracking
                    await self.detect_and_track_tool_usage(
                        process_id, agent_name, content
                    )

                    # Also log to telemetry if available
                    await self.telemetry.update_agent_activity(
                        process_id,
                        agent_name,
                        "analysis_response",
                        f"Analysis phase response: {content[:200]}...",
                    )
                except Exception as e:
                    print(f"⚠️ [ANALYSIS CALLBACK ERROR] {e}")
                    # Continue execution even if callback fails

            print(
                f"DEBUG: Before async with - self._kernel_agent = {self.kernel_agent}"
            )
            print(f"DEBUG: kernel_agent type: {type(self.kernel_agent)}")
            print(f"DEBUG: kernel_agent id: {id(self.kernel_agent)}")

            async with self.create_task_local_mcp_context() as mcp_context:
                # Create analysis orchestrator with proper agent setup using step's MCP context
                analysis_orchestrator = AnalysisOrchestrator(
                    kernel_agent=self.kernel_agent, process_context=context_data
                )

                print(
                    f"DEBUG: After AnalysisOrchestrator creation - self._kernel_agent = {self.kernel_agent}"
                )
                # Pass the step's MCP context to orchestrator instead of letting it create its own
                self._orchestrator = await analysis_orchestrator.create_analysis_orchestration_with_context(
                    mcp_context,
                    context_data,
                    agent_response_callback=agent_response_callback,
                    telemetry=self.telemetry,
                )

                logger.info(
                    f"[FOLDER] Analysis will process ({process_id}): {source_file_folder} -> {output_file_folder}"
                )

                await self.execute_analysis(context=context, context_data=context_data)

            print(f"DEBUG: After async with - self._kernel_agent = {self.kernel_agent}")

        except Exception as e:
            # State-based error handling aligned with migration service expectations
            # Migration service reads step_state.result and step_state.failure_context

            # Get error info for telemetry (no redundant dictionary needed)
            error_type = type(e).__name__
            error_message = str(e)

            # # Classify error using utility function (no temporary processor needed)
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
            #     # Let the step run naturally until it reaches AnalysisCompleted
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
            #         step_name="AnalysisStep",
            #         process_id=process_id,
            #         context_data=context_data,
            #         step_start_time=self.state.execution_start_time,
            #         step_phase="start_migration_analysis",
            #     )

            #     # Set state for migration service to read - PRIMARY failure indicator
            #     self.state.result = False
            #     self.state.reason = f"Retryable infrastructure error: {error_message}"
            #     self.state.failure_context = (
            #         await failure_collector.create_step_failure_state(
            #             reason=f"Infrastructure error (retryable): {error_message}",
            #             execution_time=time_to_failure,
            #             files_attempted=self.state.files_discovered,
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
                step_name="AnalysisStep",
                process_id=process_id,
                context_data=context_data,
                step_start_time=self.state.execution_start_time,
                step_phase="start_migration_analysis",
            )

            # Set state for migration service to read - PRIMARY failure indicator
            self.state.result = False
            self.state.reason = f"Critical error: {error_message}"
            self.state.failure_context = (
                await failure_collector.create_step_failure_state(
                    reason=f"Analysis failed: {error_message}",
                    execution_time=time_to_failure,
                    files_attempted=self.state.files_discovered,
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
        finally:
            logger.info("[SUCCESS] Analysis step execution completed")

    @kernel_function(
        description="Execute analysis phase to discover files and detect platform"
    )
    async def execute_analysis(
        self,
        context: KernelProcessStepContext,
        context_data: dict[str, Any] | None = None,
    ) -> None:
        """
        Execute analysis following single responsibility principle.

        Enhanced to provide comprehensive migration intelligence and context.

        Responsibilities:
        - Extract enhanced process context and migration parameters
        - Orchestrate group chat for file discovery and platform detection
        - Coordinate expert agents for comprehensive analysis with enhanced intelligence
        - Emit appropriate events with results
        """
        # Initialize context data if None
        if not context_data:
            context_data = {}

        # Extract simple step parameters for analysis
        is_valid, step_parameters = self._create_analysis_parameters(context_data)
        if is_valid and step_parameters:
            # Get process ID for telemetry tracking
            process_id = step_parameters.process_id

        # Track start of analysis execution
        await self.telemetry.update_agent_activity(
            process_id,
            "Conversation_Manager",
            "expert_collaboration_starting",
            f"Beginning expert collaboration for platform analysis (process {process_id})",
        )

        try:
            logger.info(
                "[TOOLS] Starting analysis phase with group chat orchestration..."
            )

            # Single responsibility: coordinate group chat analysis
            logger.info("[TARGET] Starting group chat orchestrated analysis...")

            # Ensure step_parameters is valid
            assert step_parameters is not None, (
                "step_parameters should be valid at this point"
            )

            # Parse Context Data
            source_file_folder = step_parameters.source_file_folder
            workspace_file_folder = step_parameters.workspace_file_folder
            output_file_folder = step_parameters.output_file_folder
            container_name = step_parameters.container_name

            # Check if orchestrator is available
            if not self._orchestrator:
                logger.error(
                    "[FAILED] Orchestrator not available - cannot perform analysis"
                )
                raise RuntimeError(
                    "Analysis orchestrator not initialized - critical failure"
                )
            # Define analysis task for expert agents
            analysis_task = """
            **ANALYSIS STEP OBJECTIVE**: Comprehensive source platform analysis and file discovery for Azure migration

            **SCOPE**:
            - Source folder: {{source_file_folder}}
            - Workspace folder: {{workspace_file_folder}}
            - Output folder : {{output_file_folder}}
            - Container: {{container_name}}

            **DETAILED DELIVERABLES**:
            1. **Complete File Discovery**: Catalog all YAML, JSON, and configuration files with metadata
            2. **Platform Identification**: Definitive source platform (EKS/GKE/Other) with confidence score
            3. **Multi-Dimensional Complexity Assessment**:
               - Network complexity (services, ingress, policies)
               - Security complexity (RBAC, secrets, security contexts)
               - Storage complexity (volumes, persistent storage)
               - Compute complexity (deployments, scaling, resources)
            4. **Azure Migration Readiness**: Initial assessment of migration complexity and considerations
            5. **File-by-File Analysis**: Detailed breakdown of each configuration file

            **EXPERT RESPONSIBILITIES**:
            - Chief Architect: Lead comprehensive analysis, coordinate team, provide strategic oversight
            - Platform Expert (EKS/GKE): Deep platform identification, source-specific patterns and considerations
            - Azure Expert: Azure migration context, service mapping possibilities, complexity assessment

            **SUCCESS CRITERIA**:
            - All source files discovered with complete metadata
            - Platform definitively identified with high confidence
            - Multi-dimensional complexity fully assessed
            - Azure migration pathway clearly identified

            **MANDATORY DUAL OUTPUT**:
            1. Create a comprehensive **analysis_result.md** file in {{output_file_folder}} (for human consumption)
            2. Return structured JSON data (for next step processing)

            **REQUIRED MARKDOWN REPORT STRUCTURE** (analysis_result.md):
            The analysis_result.md file must contain the following sections in markdown format:

            ## Platform Analysis Summary
            - Platform detected: [EKS/GKE/Other] with [confidence percentage]
            - Total files analyzed: [number]
            - Overall migration readiness: [assessment]

            ## File Discovery and Classification
            [Table format listing each file with type, complexity, and Azure mapping]

            ## Complexity Assessment
            ### Network Complexity
            [Description and assessment]

            ### Security Complexity
            [Description and assessment]

            ### Storage Complexity
            [Description and assessment]

            ### Compute Complexity
            [Description and assessment]

            ## Migration Readiness Analysis
            ### Overall Score: [Medium/High/Low]
            ### Key Concerns:
            - [List of concerns]

            ### Recommendations:
            - [List of recommendations]

            ## Expert Insights
            [Summary of insights from each expert team member]

            ## Next Steps
            [Recommended next steps for migration planning]

            **REQUIRED JSON RESPONSE STRUCTURE** (for next step):
            After creating the markdown file, return this JSON structure:
            ```json
            {
                "platform_detected": "EKS|GKE|Other",
                "confidence_score": "95%",
                "files_discovered": [
                    {
                        "filename": "deployment.yaml",
                        "type": "Deployment",
                        "complexity": "Medium",
                        "azure_mapping": "AKS Deployment"
                    }
                ],
                "complexity_analysis": {
                    "network_complexity": "High - Complex ingress and service mesh",
                    "security_complexity": "Medium - RBAC and secrets present",
                    "storage_complexity": "Low - Simple PVC usage",
                    "compute_complexity": "High - Multiple deployments with HPA"
                },
                "migration_readiness": {
                    "overall_score": "Medium",
                    "concerns": ["Complex networking", "Custom storage classes"],
                    "recommendations": ["Network policy review", "Storage class mapping"]
                },
                "summary": "Comprehensive analysis completed: [Platform] with [X] files analyzed",
                "expert_insights": [
                    "Chief architect provided strategic migration framework",
                    "Platform expert identified critical source platform patterns",
                    "Azure expert assessed migration complexity and service mappings"
                ],
                "analysis_file": "{{output_file_folder}}/analysis_result.md"
            }
            ```
            """

            # Using Template and replace values
            jinja_template = Template(analysis_task)
            rendered_task = jinja_template.render(
                process_id=process_id,
                source_file_folder=source_file_folder,
                workspace_file_folder=workspace_file_folder,
                output_file_folder=output_file_folder,
                container_name=container_name,
            )

            ###################################################
            # Telemetry Update (Phase already initialized by Migration Service)
            ###################################################
            if self.telemetry:
                await self.telemetry.update_agent_activity(
                    process_id,
                    "Conversation_Manager",
                    "platform_analysis_starting",
                    "Starting platform analysis with expert team",
                )

            runtime = None

            runtime = InProcessRuntime()
            runtime.start()
            await self.telemetry.update_agent_activity(
                process_id,
                "Conversation_Manager",
                "expert_collaboration",
                "Coordinating platform experts for comprehensive analysis",
            )

            orchestration_start_time = time.time()

            # NEW: Use comprehensive timing infrastructure
            # State is guaranteed to be AnalysisStepState (initialized in start_migration_analysis)
            assert self.state is not None  # Type assertion for type checker
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
                f"Expert discussion initiated for process {process_id} analyzing folder: {source_file_folder}",
            )

            # Run the orchestration using the orchestrator
            await self.telemetry.update_agent_activity(
                process_id,
                "Conversation_Manager",
                "experts_collaborating",
                "Platform experts actively analyzing source files and configurations",
            )

            orchestration_result = await self._orchestrator.invoke(
                task=rendered_task, runtime=runtime
            )

            # NEW: Use comprehensive timing infrastructure for orchestration completion
            self._ensure_state_initialized()
            self.state.set_orchestration_end()
            if self.state.orchestration_duration is not None:
                logger.info(
                    f"[TIMING] Orchestration completed in {self.state.orchestration_duration:.2f} seconds"
                )
            # else:
            #     # Fallback for legacy timing
            #     orchestration_end_time = time.time()
            #     orchestration_duration = (
            #         orchestration_end_time - orchestration_start_time
            #     )
            #     logger.info(
            #         f"[TIMING] Orchestration completed in {orchestration_duration:.2f} seconds"
            #     )

            # Track successful orchestration invocation
            await self.telemetry.update_agent_activity(
                process_id,
                "Conversation_Manager",
                "collaboration_invoked",
                "Expert collaboration session initiated successfully",
            )

            # Get Analysis Result from orchestration result
            await self.telemetry.update_agent_activity(
                process_id,
                "Conversation_Manager",
                "consensus_building",
                "Building expert consensus from analysis results",
            )

            _ = await orchestration_result.get()

            await self.telemetry.update_agent_activity(
                process_id,
                "Conversation_Manager",
                "consensus_retrieved",
                "Expert consensus successfully retrieved from discussion",
            )

            orchestration_end_time = time.time()
            orchestration_duration = orchestration_end_time - orchestration_start_time

            ##############################################################
            # Make a result file
            ##############################################################
            # Termination Result file
            # analysis_result.metadata['termination_reason']
            # analysis_result.metadata['filter_result_reason']
            # analysis_step_output = self._orchestrator.manager.final_termination_result
            # analysis_step_output.termination_reason = analysis_step_output.metadata['termination_reason']
            # analysis_step_output.filter_result_reason = analysis_step_output.metadata['filter_result_reason']

            # Add null safety checks for critical objects
            if self.telemetry:
                await self.telemetry.update_agent_activity(
                    process_id,
                    "Conversation_Manager",
                    "consensus_validation_started",
                    "Starting validation of expert consensus on analysis results",
                )

            if not self._orchestrator or not self._orchestrator._manager:
                await self.telemetry.update_agent_activity(
                    process_id,
                    "Conversation_Manager",
                    "validation_failed",
                    "Expert consensus validation failed - missing required analysis data",
                )
                logger.error(
                    "[FAILED] Orchestrator or manager is None - cannot retrieve analysis results"
                )
                raise RuntimeError("Orchestrator or manager not properly initialized")

            analysis_output = self._orchestrator._manager.final_termination_result  # type: ignore

            if analysis_output is None:
                await self.telemetry.update_agent_activity(
                    process_id,
                    "Conversation_Manager",
                    "consensus_validation_failed",
                    "Expert consensus is missing - discussion may have failed",
                )
                logger.error(
                    "[FAILED] Analysis output is None - orchestration may have failed"
                )
                raise RuntimeError("Analysis orchestration failed to produce results")

            if analysis_output.is_hard_terminated:
                # SCENARIO 1: Hard termination -> PERMANENT FAILURE (using new pattern)
                logger.info(
                    "[PERMANENT_FAILURE] Hard termination detected - processing as permanent failure"
                )
                await self._process_hard_termination_as_failure(
                    analysis_output, process_id
                )
            else:
                # Happy path: soft termination = successful completion
                await self.telemetry.update_agent_activity(
                    process_id,
                    "Conversation_Manager",
                    "consensus_processing",
                    "Processing successful expert consensus - validating platform analysis",
                )

                # Validate that we have COMPLETE termination_output for successful completion
                if analysis_output.termination_output is None:
                    await self.telemetry.update_agent_activity(
                        process_id,
                        "Conversation_Manager",
                        "consensus_validation_failed",
                        "Expert consensus completed but missing required data - experts did not provide platform analysis",
                    )
                    logger.error(
                        "[FAILED] Analysis completed successfully but termination_output is None - agent did not provide required data"
                    )
                    raise RuntimeError(
                        "Analysis agent failed to populate termination_output. All success cases must include: platform_detected, confidence_score, files_discovered, expert_insights, analysis_file"
                    )

                # Validate all required fields are populated (not None, not empty)
                validation_errors = []

                if not analysis_output.termination_output.platform_detected:
                    validation_errors.append("platform_detected is missing or empty")
                if not analysis_output.termination_output.confidence_score:
                    validation_errors.append("confidence_score is missing or empty")
                if analysis_output.termination_output.files_discovered is None:
                    validation_errors.append(
                        "files_discovered is None (should be array)"
                    )
                if not analysis_output.termination_output.expert_insights:
                    validation_errors.append("expert_insights is missing or empty")
                if not analysis_output.termination_output.analysis_file:
                    validation_errors.append("analysis_file is missing or empty")

                if validation_errors:
                    await self.telemetry.update_agent_activity(
                        process_id,
                        "Conversation_Manager",
                        "consensus_validation_failed",
                        f"Expert consensus validation failed: {', '.join(validation_errors)}",
                    )
                    logger.error(
                        "[FAILED] Analysis termination_output validation failed: %s",
                        ", ".join(validation_errors),
                    )
                    raise RuntimeError(
                        f"Analysis agent provided incomplete termination_output. Missing/empty fields: {', '.join(validation_errors)}. "
                        "All fields must be populated for successful completion."
                    )

                # Validation successful
                await self.telemetry.update_agent_activity(
                    process_id,
                    "Conversation_Manager",
                    "consensus_validated",
                    f"Expert consensus validated: platform_detected={analysis_output.termination_output.platform_detected}, files_discovered ({len(analysis_output.termination_output.files_discovered or [])} files)",
                )

                # Track successful completion
                await self.telemetry.update_agent_activity(
                    process_id,
                    "Conversation_Manager",
                    "consensus_reached",
                    f"Expert consensus reached: {analysis_output.termination_output.platform_detected} platform identified with {len(analysis_output.termination_output.files_discovered or [])} files",
                )

                # Create structured result
                # Safely extract discovered files, handling case where termination_output might be None
                # Use validated termination_output data
                self._ensure_state_initialized()
                assert self.state is not None  # For type checker
                self.state.platform_detected = (
                    analysis_output.termination_output.platform_detected
                )
                self.state.files_discovered = (
                    analysis_output.termination_output.files_discovered
                )

                discovered_files = []
                if analysis_output.termination_output and hasattr(
                    analysis_output.termination_output, "files_discovered"
                ):
                    discovered_files = (
                        analysis_output.termination_output.files_discovered or []
                    )

                result = {
                    "process_id": process_id,
                    "source_file_folder": source_file_folder,
                    "workspace_file_folder": workspace_file_folder,
                    "output_file_folder": output_file_folder,
                    "container_name": container_name,
                    "result_file_name": "analysis_result.md",
                    "state": analysis_output,
                    "execution_time_seconds": orchestration_duration,
                    "discovered_files": discovered_files,
                }

                ############################################################
                # Set up Step Values
                ############################################################
                self._ensure_state_initialized()
                assert self.state is not None  # For type checker
                self.state.name = "AnalysisStepState"
                self.state.id = "Analysis"
                self.state.version = "1.0"
                self.state.result = True
                self.state.analysis_completed = True
                self.state.files_discovered = discovered_files
                self.state.platform_detected = (
                    analysis_output.termination_output.platform_detected
                )
                self.state.final_result = analysis_output
                self.state.reason = analysis_output.reason

                # NEW: Set execution end time for comprehensive timing
                # State is guaranteed to be AnalysisStepState (initialized above)
                self.state.set_execution_end()
                timing_summary = self.state.get_timing_summary()
                logger.info(
                    f"[TIMING] Analysis completed - Total execution: {self.state.total_execution_duration:.2f}s"
                )
                logger.info(f"[TIMING] Timing summary: {timing_summary}")

                # Track successful orchestration
                await self.telemetry.update_agent_activity(
                    process_id,
                    "Conversation_Manager",
                    "analysis_discussion_complete",
                    f"Expert discussion completed successfully in {self.state.orchestration_duration or orchestration_duration:.2f} seconds",
                )

                safe_log(
                    logger,
                    "info",
                    "[SUCCESS] Group chat analysis completed for process {process_id} in {duration} seconds",
                    process_id=process_id,
                    duration=f"{self.state.total_execution_duration or orchestration_duration:.2f}",
                )

                # Track step completion
                await self.telemetry.update_agent_activity(
                    process_id,
                    "Conversation_Manager",
                    "analysis_complete",
                    f"Platform analysis completed by expert team in {self.state.total_execution_duration or orchestration_duration:.2f} seconds",
                )

                # Emit success event - proper event handling
                await context.emit_event(
                    process_event="AnalysisCompleted",
                    data={
                        "process_id": context_data.get("process_id"),
                        "analysis_result": result,
                        "app_context": context_data.get("app_context"),
                    },
                )

                await asyncio.sleep(1)

        except Exception as e:
            # ORCHESTRATION-LEVEL ERROR HANDLING - Different timing context than setup errors
            logger.error(
                f"[ORCHESTRATION FAILURE] Exception during orchestration phase: {str(e)}"
            )

            # Get error info for telemetry (no redundant dictionary needed)
            error_type = type(e).__name__
            error_message = str(e)

            # error_classification = classify_error(e)

            # is_retryable = error_classification == ErrorClassification.RETRYABLE
            # is_ignorable = error_classification == ErrorClassification.IGNORABLE

            # Ensure state is initialized
            self._ensure_state_initialized()
            assert self.state is not None  # For type checker

            # Capture execution end time for comprehensive failure context
            # NOTE: This is pre-orchestration failure - only execution timing is relevant
            self.state.set_execution_end()

            # Calculate time to failure (setup + error handling time)
            time_to_failure = self.state.total_execution_duration or 0.0

            # # Handle timing based on orchestration phase
            # if self.state.orchestration_start_time is not None:
            #     # Orchestration was started - capture orchestration end timing
            #     self.state.set_orchestration_end()
            #     self.state.set_execution_end()

            #     timing_context = f"orchestration phase (ran {self.state.orchestration_duration or 0.0:.2f}s)"
            #     total_time = self.state.total_execution_duration or 0.0
            # else:
            #     # Orchestration never started - only execution timing
            #     self.state.set_execution_end()
            #     timing_context = "pre-orchestration setup"
            #     total_time = self.state.total_execution_duration or 0.0

            # Create failure context for orchestration-level errors
            failure_collector = StepFailureCollector()
            system_context = await failure_collector.collect_system_failure_context(
                error=e,
                step_name="AnalysisStep",
                process_id=process_id,
                context_data=context_data,
                step_start_time=self.state.execution_start_time,
                step_phase="execute_analysis_orchestration",
            )

            # Set comprehensive failure state
            self.state.result = False
            self.state.reason = f"Orchestration failed: {error_message}"
            self.state.failure_context = (
                await failure_collector.create_step_failure_state(
                    reason=f"Analysis failed: {error_message}",
                    execution_time=time_to_failure,
                    files_attempted=self.state.files_discovered,
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
                f"[ORCHESTRATION FAILURE] State updated with failure context - total time: {time_to_failure:.2f}s in analysis"
            )

            # Don't re-raise - let migration service read the failure context
            return

        finally:
            # Always clean up runtime if it was created
            try:
                if runtime is not None:
                    await runtime.stop_when_idle()
                    logger.info("[CLEANUP] Analysis runtime cleaned up")
            except NameError:
                # runtime was never created due to early exception
                pass
