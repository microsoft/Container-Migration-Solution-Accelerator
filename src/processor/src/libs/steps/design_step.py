"""
Design Step - Single responsibility: Create Azure architecture recommendations.

Following SK Process Framework best practices:
- Single responsibility principle
- Proper event handling with error management
- Isolated kernel instance
- Clear input/output via events
- Step-specific group chat orchestration
"""

import time
from typing import Any

from jinja2 import Template
from pydantic import BaseModel, Field, computed_field
from semantic_kernel.agents import GroupChatOrchestration
from semantic_kernel.agents.runtime import InProcessRuntime
from semantic_kernel.contents import ChatMessageContent
from semantic_kernel.functions import kernel_function
from semantic_kernel.processes.kernel_process import (
    KernelProcessStep,
    KernelProcessStepContext,
    KernelProcessStepState,
)

from libs.application.application_context import AppContext
from libs.base.KernelAgent import semantic_kernel_agent
from libs.steps.base_step_state import BaseStepState
from libs.steps.orchestration.design_orchestration import (
    DesignOrchestrator,
)
from libs.steps.orchestration.models.analysis_result import (
    Analysis_ExtendedBooleanResult,
    AnalysisOutput,
    ComplexityAnalysis,
    FileType,
    MigrationReadiness,
)
from libs.steps.orchestration.models.design_result import (
    Design_ExtendedBooleanResult,
)
from libs.steps.step_failure_collector import StepFailureCollector
from plugins.mcp_server import MCPBlobIOPlugin, MCPDatetimePlugin, MCPMicrosoftDocs
from utils.agent_telemetry import ProcessStatus, TelemetryManager
from utils.error_classifier import ErrorClassification, classify_error
from utils.logging_utils import create_migration_logger, safe_log
from utils.mcp_context import PluginContext, with_name
from utils.tool_tracking import ToolTrackingMixin

logger = create_migration_logger(__name__)


class DesignStepState(BaseStepState):
    """State for the Design step following best practices."""

    # Base fields required by KernelProcessStepState
    name: str = Field(default="DesignStepState", description="Name of the step state")
    version: str = Field(default="1.0", description="Version of the step state")
    reason: str = Field(default="", description="Reason for failure if any")
    architecture_created: list[str] = []
    recommendations: list[str] = []
    design_completed: bool = False
    final_result: Design_ExtendedBooleanResult | None = None
    result: bool | None = None  # None = not started, True = success, False = failed

    requires_immediate_retry: bool = Field(default=False)
    termination_details: dict[str, Any] | None = Field(default=None)


class design_parameter(BaseModel):
    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}

    # Core process context
    process_id: str
    source_file_folder: str
    workspace_file_folder: str
    output_file_folder: str
    container_name: str
    app_context: AppContext

    # Analysis results for design context - directly from analysis step
    analysis_result: AnalysisOutput  # Changed to proper model type
    platform_detected: str = Field(default="Unknown")
    confidence_score: str = Field(default="0%")  # Fixed typo from confident_score
    files_discovered: list[FileType]
    complexity_analysis: ComplexityAnalysis
    migration_readiness: MigrationReadiness

    # Design-specific parameters - computed from analysis results
    migration_type: str = Field(default="Unknown to Azure AKS migration")
    target_platform: str = Field(default="Azure AKS")
    overall_complexity: str = Field(default="Medium")

    # Computed field that automatically calculates files count based on files_discovered
    @computed_field
    @property
    def files_count(self) -> int:
        """Automatically calculate the number of discovered files."""
        return (
            len(self.files_discovered) if isinstance(self.files_discovered, list) else 0
        )


class DesignStep(KernelProcessStep[DesignStepState], ToolTrackingMixin):
    """
    Design step that creates Azure architecture recommendations.

    Following SK Process Framework best practices:
    - Single responsibility: architecture design only
    - Isolated kernel instance to prevent recursive invocation
    - Proper error handling and event emission
    - Simple, focused functionality
    """

    # For Pydantic model validation
    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}

    state: DesignStepState | None = Field(
        default_factory=lambda: DesignStepState(name="DesignStepState", version="1.0")
    )

    def create_task_local_mcp_context(self) -> PluginContext:
        """
        # TODO: Consolidate repeatable code patterns

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
            "[TOOLS] DESIGN STEP CONSTRUCTOR: Starting synchronous initialization..."
        )
        self.kernel_agent = None
        self._orchestrator: GroupChatOrchestration | None = None

        logger.info(
            "[SUCCESS] DESIGN STEP CONSTRUCTOR: Synchronous initialization complete"
        )

    # async def _update_agent_activity_async(
    #     self, process_id, agent_name: str, action: str, message: str = ""
    # ):
    #     """Update agent activity using instance telemetry if available, otherwise use global."""
    #     if self.telemetry and hasattr(self.telemetry, "update_agent_activity"):
    #         await self.telemetry.update_agent_activity(
    #             process_id=process_id,
    #             agent_name=agent_name,
    #             action=action,
    #             message_preview=message,
    #         )

    def _extract_comprehensive_step_parameters(
        self, context_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Extract comprehensive parameters from context data including analysis results.
        Design step builds on analysis results to create architecture recommendations.

        The context_data structure is:
        {
            "process_id": "...",
            "analysis_result": {
                "state": Analysis_ExtendedBooleanResult {
                    "termination_output": AnalysisOutput {...}
                }
            }
        }
        """

        #  result = {
        #             "process_id": process_id,
        #             "source_file_folder": source_file_folder,
        #             "workspace_file_folder": workspace_file_folder,
        #             "output_file_folder": output_file_folder,
        #             "container_name": container_name,
        #             "result_file_name": "analysis_result.md",
        #             "state": analysis_output,
        #             "execution_time_seconds": orchestration_duration,
        #             "discovered_files": discovered_files,
        #         }

        analysis_result = context_data.get("analysis_result")

        #########################################################
        # Extract core parameters from context data
        ##########################################################

        # Extract base parameters
        # Process core context
        process_id = context_data.get("process_id")
        app_context = context_data.get("app_context")
        source_file_folder = analysis_result.get("source_file_folder")
        workspace_file_folder = analysis_result.get("workspace_file_folder")
        output_file_folder = analysis_result.get("output_file_folder")
        container_name = analysis_result.get("container_name")

        # analysis_termination_output = analysis_state.termination_output

        # Extract analysis results with safe defaults
        if analysis_result:
            analysis_state: Analysis_ExtendedBooleanResult = analysis_result.get(
                "state"
            )
        return {
            "process_id": process_id,
            "app_context": app_context,
            "source_file_folder": source_file_folder,
            "workspace_file_folder": workspace_file_folder,
            "output_file_folder": output_file_folder,
            "container_name": container_name,
            "analysis_result": analysis_result,
            "platform_detected": analysis_state.termination_output.platform_detected
            if analysis_state and analysis_state.termination_output
            else "Unknown",
            "confidence_score": analysis_state.termination_output.confidence_score
            if analysis_state and analysis_state.termination_output
            else "0%",
            "files_discovered": analysis_state.termination_output.files_discovered
            if analysis_state and analysis_state.termination_output
            else [],
            "complexity_analysis": analysis_state.termination_output.complexity_analysis
            if analysis_state and analysis_state.termination_output
            else {},
            "migration_readiness": analysis_state.termination_output.migration_readiness
            if analysis_state and analysis_state.termination_output
            else {},
            # Design-specific parameters
            "migration_type": f"{analysis_state.termination_output.platform_detected if analysis_state and analysis_state.termination_output else 'Unknown'} to Azure AKS migration",
            "target_platform": "Azure AKS",
            "files_count": len(analysis_state.termination_output.files_discovered),
            # Note: files_count is now computed automatically by the design_parameter model
            "overall_complexity": analysis_state.termination_output.migration_readiness.overall_score
            if analysis_state
            and analysis_state.termination_output
            and analysis_state.termination_output.migration_readiness
            else "Medium",
        }

        # return design_parameter(
        #     **{
        #         # Core process context
        #         "process_id": process_id,
        #         "source_file_folder": source_file_folder,
        #         "workspace_file_folder": workspace_file_folder,
        #         "output_file_folder": output_file_folder,
        #         "container_name": container_name,
        #         "app_context": app_context,
        #         # Analysis results for design context
        #         "analysis_result": analysis_result,
        #         "platform_detected": analysis_state.termination_output.platform_detected
        #         if analysis_state and analysis_state.termination_output
        #         else "Unknown",
        #         "confidence_score": analysis_state.termination_output.confidence_score
        #         if analysis_state and analysis_state.termination_output
        #         else "0%",
        #         "files_discovered": analysis_state.termination_output.files_discovered
        #         if analysis_state and analysis_state.termination_output
        #         else [],
        #         "complexity_analysis": analysis_state.termination_output.complexity_analysis
        #         if analysis_state and analysis_state.termination_output
        #         else {},
        #         "migration_readiness": analysis_state.termination_output.migration_readiness
        #         if analysis_state and analysis_state.termination_output
        #         else {},
        #         # Design-specific parameters
        #         "migration_type": f"{analysis_state.termination_output.platform_detected if analysis_state and analysis_state.termination_output else 'Unknown'} to Azure AKS migration",
        #         "target_platform": "Azure AKS",
        #         # Note: files_count is now computed automatically by the design_parameter model
        #         "overall_complexity": analysis_state.termination_output.migration_readiness.overall_score
        #         if analysis_state
        #         and analysis_state.termination_output
        #         and analysis_state.termination_output.migration_readiness
        #         else "Medium",
        #     }

    async def activate(self, state: KernelProcessStepState[DesignStepState]):
        """
        Activate the step for state initialization only.

        Note: Kernel agent creation moved to start_design_from_analysis() for lazy initialization.
        This avoids unnecessary resource allocation for steps that may never execute.
        """
        self.state = state.state
        # Ensure state is never None
        self._ensure_state_initialized()

    def _ensure_state_initialized(self) -> None:
        """Ensure state is properly initialized before use."""
        if self.state is None:
            self.state = DesignStepState(name="DesignStepState", version="1.0")

    async def _validate_reasoning_quality(self, termination_output) -> None:
        """
        Validate reasoning quality to prevent hallucination patterns.

        Checks for evidence-based reasoning vs generic excuses.
        """
        hallucination_patterns = [
            "limited analysis data",
            "require deeper investigation",
            "complex configurations",
            "advanced settings need",
            "insufficient details",
            "further investigation needed",
        ]

        evidence_patterns = [
            "check_blob_exists",
            "list_blobs_in_container",
            "read_blob_content",
            "returned:",
            "got error:",
            "file not found",
            "access denied",
            "empty folder",
        ]

        if termination_output.incomplete_reason:
            reason_lower = termination_output.incomplete_reason.lower()
            process_id = termination_output.process_id

            # Check for hallucination patterns
            has_hallucination = any(
                pattern in reason_lower for pattern in hallucination_patterns
            )
            has_evidence = any(pattern in reason_lower for pattern in evidence_patterns)

            if has_hallucination and not has_evidence:
                logger.warning(
                    "[ANTI-HALLUCINATION] Reasoning appears generic without tool evidence: %s",
                    termination_output.incomplete_reason[:200] + "..."
                    if len(termination_output.incomplete_reason) > 200
                    else termination_output.incomplete_reason,
                )
                if self.telemetry:
                    await self.telemetry.update_agent_activity(
                        process_id,
                        "Conversation_Manager",
                        "expert_reasoning_quality_warning",
                        "Expert reasoning appears generic - recommend using MCP tools for verification",
                    )
            elif has_evidence:
                logger.info(
                    "[ANTI-HALLUCINATION] Evidence-based reasoning detected - good quality"
                )
                if self.telemetry:
                    await self.telemetry.update_agent_activity(
                        process_id,
                        "Conversation_Manager",
                        "expert_reasoning_quality_good",
                        "Evidence-based reasoning provided with expert tool verification",
                    )

    def _create_termination_context_data(self, design_output) -> dict[str, Any]:
        """Create context data for termination failure scenarios"""
        context_data = {
            "termination_type": design_output.termination_type,
            "termination_reason": design_output.reason,
            "blocking_issues": list(design_output.blocking_issues) if design_output.blocking_issues else [],
        }

        # Add termination output details if available
        if design_output.termination_output:
            context_data.update({
                "azure_services": design_output.termination_output.azure_services or [],
                "architecture_decisions": design_output.termination_output.architecture_decisions or [],
                "expert_insights": design_output.termination_output.expert_insights or [],
            })

        return context_data

    async def _process_hard_termination_as_failure(
        self, design_output, process_id: str
    ) -> None:
        """Process ALL hard terminations as permanent failures using existing error infrastructure"""
        # Extract design decisions safely
        architecture_created = (
            design_output.termination_output.azure_services or []
            if design_output.termination_output
            else []
        )

        # Step 1: Update telemetry with failure notification
        await self.telemetry.update_agent_activity(
            process_id,
            "Conversation_Manager",
            "design_permanently_failed",
            f"Design failed permanently due to {design_output.termination_type}: {design_output.reason}. Expert consensus: {design_output.blocking_issues}"
        )

        # Step 2: Create failure context using existing StepFailureCollector
        # Create "virtual exception" for termination scenario
        termination_error = ValueError(f"Hard termination: {design_output.termination_type} - {design_output.reason}")

        # Use existing StepFailureCollector
        failure_collector = StepFailureCollector()
        system_context = await failure_collector.collect_system_failure_context(
            error=termination_error,
            step_name="DesignStep",
            process_id=process_id,
            context_data=self._create_termination_context_data(design_output),
            step_start_time=self.state.execution_start_time,
            step_phase="hard_termination_design"
        )

        # Step 3: Set failure state (NOT retry state)
        self._ensure_state_initialized()
        assert self.state is not None  # For type checker

        # Set up basic state (similar to current logic but as FAILURE)
        self.state.name = "DesignStepState"
        self.state.id = "Design"
        self.state.version = "1.0"
        self.state.result = False  # FAILURE, not retry
        self.state.design_completed = False
        self.state.architecture_created = architecture_created
        self.state.recommendations = (
            design_output.termination_output.architecture_decisions or []
            if design_output.termination_output
            else []
        )
        self.state.final_result = design_output
        self.state.reason = f"Hard termination: {design_output.termination_type} - {design_output.reason}"

        # Set failure context using existing infrastructure
        self.state.failure_context = await failure_collector.create_step_failure_state(
            reason=f"Design terminated: {design_output.termination_type} - {design_output.reason}",
            execution_time=self.state.total_execution_duration or 0.0,
            files_attempted=architecture_created,
            system_failure_context=system_context
        )

        # CRITICAL: Do NOT set retry flags
        # self.state.requires_immediate_retry = False (default)
        # No termination_details for retry

        # Step 4: Record failure outcome in telemetry
        failure_details = {
            "termination_type": design_output.termination_type,
            "termination_reason": design_output.reason,
            "blocking_issues": design_output.blocking_issues,
            "architecture_created": len(architecture_created),
            "handled_as": "permanent_failure"
        }

        await self.telemetry.update_agent_activity(
            process_id,
            "Design_Expert",
            "step_permanently_failed",
            f"Design step terminated permanently: {failure_details}"
        )

    @kernel_function(description="Handle design event from analysis completion")
    async def start_design_from_analysis(
        self, context: KernelProcessStepContext, context_data: dict[str, Any]
    ) -> None:
        """
        Handle the AnalysisCompleted event and delegate to execute_design.

        This function extracts parameters from the context_data and calls execute_design.
        Each step creates its own PluginContext for clean isolation.
        """
        # Extract process_id for telemetry tracking
        process_id = context_data.get("process_id", "default-process-id")
        parameters = self._extract_comprehensive_step_parameters(context_data)
        # analysis_state: Analysis_ExtendedBooleanResult = parameters["analysis_result"]["state"]
        analysis_result: AnalysisOutput = parameters["analysis_result"]
        self.telemetry = TelemetryManager(parameters["app_context"])

        # Lazy initialization: Create kernel agent only when step actually needs to execute
        if self.kernel_agent is None:
            logger.info("[TOOLS] DESIGN STEP: Creating kernel agent for execution...")
            self.kernel_agent = semantic_kernel_agent(
                env_file_path=None,  # Do not load .env file
                custom_service_prefixes=None,
                use_entra_id=True,
            )
            logger.info("[TOOLS] DESIGN STEP: About to initialize kernel agent...")
            await self.kernel_agent.initialize_async()
            logger.info("[SUCCESS] DESIGN STEP: Kernel agent ready for execution")

        logger.info(
            "[SUCCESS] DESIGN STEP ACTIVATE: Step state initialized (kernel agent will be created when needed)"
        )

        try:
            logger.info(
                "[START] Received AnalysisCompleted event, starting design with lazy kernel agent initialization..."
            )

            # NEW: Use comprehensive timing infrastructure for execution tracking
            self._ensure_state_initialized()
            assert self.state is not None  # For type checker
            self.state.set_execution_start()

            # Phase update Telemetry

            # Transition to Design phase
            if self.telemetry:
                await self.telemetry.transition_to_phase(
                    process_id=process_id, phase="Design", step="Design"
                )
                await self.telemetry.update_agent_activity(
                    process_id=process_id,
                    agent_name="Conversation_Manager",
                    action="design_discussion_starting",
                    message_preview="Starting expert discussion for Azure architecture design",
                )

                # Initialize step-level telemetry - moved here as this is when step actually starts
                await self.telemetry.update_agent_activity(
                    process_id=process_id,
                    agent_name="Conversation_Manager",
                    action="design_experts_assembling",
                    message_preview=f"Assembling architecture experts for design discussion (process {process_id})",
                )

                # Update agent activity with instance telemetry if available
                await self.telemetry.update_agent_activity(
                    process_id=process_id,
                    agent_name="Conversation_Manager",
                    action="architecture_discussion_starting",
                    message_preview="Starting architecture discussion for Azure recommendations",
                )

            # Extract parameters from context_data
            process_id = process_id
            analysis_result = analysis_result
            source_file_folder = parameters["source_file_folder"]
            output_file_folder = parameters["output_file_folder"]

            async def agent_response_callback(message: ChatMessageContent):
                # Handle agent responses specific to the design step
                print("🚨🚨🚨 CALLBACK INVOKED!!! 🚨🚨🚨")

                try:
                    # Try to extract agent name from multiple possible sources
                    agent_name = None

                    # First try the message name
                    if hasattr(message, "name") and message.name:
                        agent_name = message.name

                    # Try to extract from role if available
                    if (
                        not agent_name
                        and hasattr(message, "role")
                        and message.role
                        and hasattr(message.role, "value")
                    ):
                        role_value = message.role.value
                        # If role contains agent identifier, use it
                        if any(
                            agent in role_value
                            for agent in [
                                "Chief_Architect",
                                "Azure_Expert",
                                "EKS_Expert",
                                "GKE_Expert",
                            ]
                        ):
                            agent_name = role_value

                    # Try to extract from content if it contains agent signatures
                    content = getattr(message, "content", "")
                    if not agent_name and content:
                        # Look for agent names in content patterns
                        for potential_agent in [
                            "Chief_Architect",
                            "Azure_Expert",
                            "EKS_Expert",
                            "GKE_Expert",
                        ]:
                            if potential_agent.lower() in content.lower()[:200]:
                                agent_name = potential_agent
                                break

                    # Clean agent name by removing internal ID suffixes
                    if agent_name:
                        # Handle names like "Chief_Architect_823da78df38c49f6aa10adf347e155d3"
                        # Extract the clean agent name before any UUID-like suffix
                        import re

                        # Match pattern: AgentName_[32-char hex string]
                        clean_name_match = re.match(
                            r"(Chief_Architect|Azure_Expert|EKS_Expert|GKE_Expert)(?:_[a-f0-9]{32})?",
                            agent_name,
                        )
                        if clean_name_match:
                            agent_name = clean_name_match.group(1)
                        else:
                            # Fallback: try to find any of our expected agent names at the start
                            for expected_agent in [
                                "Chief_Architect",
                                "Azure_Expert",
                                "EKS_Expert",
                                "GKE_Expert",
                            ]:
                                if agent_name.startswith(expected_agent):
                                    agent_name = expected_agent
                                    break

                    # Fallback to a generic agent name with step context
                    if not agent_name:
                        agent_name = "Design_Agent_Unknown"

                    # Final validation - ensure we have a valid agent name
                    if agent_name and agent_name not in [
                        "Chief_Architect",
                        "Azure_Expert",
                        "EKS_Expert",
                        "GKE_Expert",
                    ]:
                        # If we got something like "Assistant" or similar, map it to our expected agents
                        # Default to Chief_Architect for design step coordination
                        agent_name = "Chief_Architect"

                    print(f"🎨 [DESIGN CALLBACK] Agent: {agent_name}")
                    print(f"🎨 [DESIGN CALLBACK] Content: {content[:200]}...")
                    print(f"🎨 [DESIGN CALLBACK] Message Type: {type(message)}")
                    print(
                        f"🎨 [DESIGN CALLBACK] Message Attrs: {[attr for attr in dir(message) if not attr.startswith('_')]}"
                    )

                    # Enhanced tool usage detection and tracking
                    await self.detect_and_track_tool_usage(
                        process_id, agent_name, content
                    )

                    # Detailed callback debugging
                    print(
                        f"🔧 [CALLBACK DEBUG] About to call update_agent_activity for {agent_name}"
                    )
                    print("🔧 [CALLBACK DEBUG] Action: design_response")
                    print(f"🔧 [CALLBACK DEBUG] Content preview: {content[:100]}...")

                    print(
                        f"🔧 [CALLBACK DEBUG] Telemetry manager exists: {self.telemetry is not None}"
                    )

                    current_process: ProcessStatus | None = None
                    if self.telemetry:
                        current_process = await self.telemetry.get_current_process(
                            process_id=process_id
                        )
                        if current_process:
                            agents_before = list(current_process.agents.keys())
                            print(
                                f"🔧 [CALLBACK DEBUG] Current agents before update: {agents_before}"
                            )
                        await self.telemetry.update_agent_activity(
                            process_id,
                            agent_name,
                            "design_response",
                            f"Design phase response: {content[:200]}...",
                        )

                    # Debug agent state after update
                    if self.telemetry and current_process:
                        agents_after = list(current_process.agents.keys())
                        print(
                            f"🔧 [CALLBACK DEBUG] Current agents after update: {agents_after}"
                        )
                        if agent_name in current_process.agents:
                            agent_data = current_process.agents[agent_name]
                            print(
                                f"🔧 [CALLBACK DEBUG] {agent_name} data: action={agent_data.current_action}, active={agent_data.is_active}"
                            )

                except Exception as e:
                    print(f"⚠️ [DESIGN CALLBACK ERROR] {e}")
                    # Continue execution even if callback fails

            async with self.create_task_local_mcp_context() as mcp_context:
                # Create design orchestrator with proper agent setup using step's MCP context
                design_orchestrator = DesignOrchestrator(
                    kernel_agent=self.kernel_agent, process_context=context_data
                )
                # Pass the step's MCP context to orchestrator instead of letting it create its own
                self._orchestrator = (
                    await design_orchestrator.create_design_orchestration_with_context(
                        mcp_context=mcp_context,
                        process_context=context_data,
                        agent_response_callback=agent_response_callback,
                        telemetry=self.telemetry,
                    )
                )
                logger.info(
                    f"[FOLDER] Design will process ({process_id}): {source_file_folder} -> {output_file_folder}"
                )

                # Delegate to the main design function
                await self.execute_design(context=context, context_data=context_data)

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
            #     # Let the step run naturally until it reaches DesignCompleted
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
            #         step_name="DesignStep",
            #         process_id=process_id,
            #         context_data=context_data,
            #         step_start_time=self.state.execution_start_time,
            #         step_phase="start_design_from_analysis",
            #     )

            #     # Set state for migration service to read - PRIMARY failure indicator
            #     self.state.result = False
            #     self.state.reason = f"Retryable infrastructure error: {error_message}"
            #     self.state.failure_context = (
            #         await failure_collector.create_step_failure_state(
            #             reason=f"Infrastructure error (retryable): {error_message}",
            #             execution_time=time_to_failure,
            #             files_attempted=self.state.architecture_created,
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
                step_name="DesignStep",
                process_id=process_id,
                context_data=context_data,
                step_start_time=self.state.execution_start_time,
                step_phase="start_design_from_analysis",
            )

            # Set state for migration service to read - PRIMARY failure indicator
            self.state.result = False
            self.state.reason = f"Critical error: {error_message}"
            self.state.failure_context = (
                await failure_collector.create_step_failure_state(
                    reason=f"Design failed: {error_message}",
                    execution_time=time_to_failure,
                    files_attempted=self.state.architecture_created,
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

    @kernel_function(description="Execute design phase to create Azure architecture")
    async def execute_design(
        self,
        context: KernelProcessStepContext,
        context_data: dict[str, Any] | None = None,
    ) -> None:
        """
        Execute design following single responsibility principle.

        Responsibilities:
        - Orchestrate group chat for Azure architecture design
        - Coordinate expert agents for comprehensive design
        - Emit appropriate events with results
        """
        # Get process ID for telemetry tracking
        process_id = (
            context_data.get("process_id", "default-process-id")
            if context_data
            else "default-process-id"
        )

        # Initialize context data if None
        if not context_data:
            context_data = {}

        # Extract comprehensive step parameters including analysis results
        parameters = self._extract_comprehensive_step_parameters(context_data)

        # Track start of design execution with analysis context
        if self.telemetry:
            await self.telemetry.update_agent_activity(
                "Conversation_Manager",
                "expert_design_starting",
                f"Beginning expert architecture design discussion for {parameters['migration_type']} with {parameters['files_count']} files analyzed",
            )

        try:
            logger.info("[ART] Starting design phase with group chat orchestration...")

            # Single responsibility: coordinate group chat design
            logger.info("[TARGET] Starting group chat orchestrated design...")

            # Parse Context Data from comprehensive parameters
            # process_id = parameters.process_id
            # source_file_folder = parameters.source_file_folder
            # workspace_file_folder = parameters.workspace_file_folder
            # output_file_folder = parameters.output_file_folder
            # container_name = parameters.container_name
            # files_discovered = parameters.files_discovered
            # platform_detected = parameters.platform_detected
            # confidence_score = parameters.confidence_score
            # migration_type = parameters.migration_type
            # complexity_analysis = parameters.complexity_analysis
            # migration_readiness = parameters.migration_readiness
            # target_platform = parameters.target_platform
            # files_count = parameters.files_count
            # overall_complexity = parameters.overall_complexity

            # Check if orchestrator is available
            if not self._orchestrator:
                logger.error(
                    "[FAILED] Orchestrator not available - cannot perform design"
                )
                raise RuntimeError(
                    "Design orchestrator not initialized - critical failure"
                )

            # Define enhanced design task leveraging analysis results
            design_task = """
            **🎯 COMPREHENSIVE AZURE ARCHITECTURE DESIGN OBJECTIVE**: Create intelligent Azure architecture recommendations based on detailed analysis results

            **📊 ANALYSIS INTELLIGENCE CONTEXT**:
            - Migration Type: {{migration_type}}
            - Source Platform: {{platform_detected}} (Confidence: {{confidence_score}})
            - Target Platform: {{target_platform}}
            - Files Analyzed: {{files_count}} configuration files
            - Analyzed Files: {{files_discovered}}
            - Source Folder(Kubernetes manifest files) : {{source_file_folder}}
            - Overall Complexity: {{overall_complexity}}


            **📁 DESIGN SCOPE**:
            - Analysis Results: {{output_file_folder}}/analysis_result.md
            - Source folder: {{source_file_folder}}
            - Workspace folder: {{workspace_file_folder}}
            - Output folder: {{output_file_folder}}
            - Container: {{container_name}}

            **🔍 ANALYSIS-DRIVEN DESIGN FOUNDATION**:
            Based on analysis results, focus on these key complexity areas:
            - Azure Well-Architected Framework(WAF) aligned
            - Network Complexity: {{network_complexity}}
            - Security Complexity: {{security_complexity}}
            - Storage Complexity: {{storage_complexity}}
            - Compute Complexity: {{compute_complexity}}

            **[TOOLS] RESEARCH-DRIVEN DESIGN METHODOLOGY**:
            You have access to comprehensive Microsoft Azure documentation tools. **ALWAYS use these research capabilities**:
            - **Azure Architecture Center**: Query for reference architectures matching {{platform_detected}} to Azure migrations
            - **Service Documentation**: Research AKS capabilities, Application Gateway, Storage solutions
            - **Migration Best Practices**: Find official {{migration_type}} approaches
            - **Security Standards**: Access Azure security baselines for {{overall_complexity}} complexity scenarios

            **BEFORE STARTING DESIGN**:
            1. Verify analysis_result.md exists: check_blob_exists('analysis_result.md', container_name='{{container_name}}', folder_path='{{output_file_folder}}')
            2. List available source files: list_blobs_in_container(container_name='{{container_name}}', folder_path='{{source_file_folder}}')
            3. If files missing, report specific missing files and request Analysis step rerun

            **TROUBLESHOOTING FILE ACCESS**:
            If you cannot access required files:
            1. List all containers: list_containers()
            2. List contents of process folder: list_blobs_in_container(container_name='{{container_name}}', folder_path='{{process_id}}', recursive=true)
            3. Check specific file: check_blob_exists('analysis_result.md', container_name='{{container_name}}', folder_path='{{output_file_folder}}')
            4. Report exact error messages and found vs expected paths

            **📋 COMPREHENSIVE DELIVERABLES**:
            1. **Intelligence-Based Service Mapping**: Map each analyzed service to optimal Azure equivalent
            2. **Complexity-Aware Architecture Design**: Address specific complexity areas identified in analysis
            3. **{{platform_detected}}-to-Azure Migration Strategy**: Tailored approach based on source platform
            4. **Risk-Informed Implementation Plan**: Address concerns identified in analysis phase

            **👥 EXPERT COORDINATION WITH ANALYSIS CONTEXT**:
            - **Chief Architect**: Strategic design leadership leveraging {{files_count}} files analysis
            - **{{platform_detected}} Expert**: Source platform expertise for accurate Azure mapping
            - **Azure Expert**: {{target_platform}} architecture optimized for {{overall_complexity}} complexity
            - **Security Architect**: Address security complexity: {{security_complexity}}

            **✅ ENHANCED SUCCESS CRITERIA**:
            - Complete Azure architecture addressing all {{files_count}} analyzed files
            - Service mappings optimized for {{platform_detected}} source patterns
            - Migration strategy tailored to {{overall_complexity}} complexity level
            - Risk mitigation for analysis-identified concerns

            **📤 MANDATORY OUTPUT**:
            - **design_result.md** in {{output_file_folder}}

            **🔧 CRITICAL: FILE CREATION STEPS**:
            1. **MUST CREATE design_result.md FILE**: Use save_content_to_blob to create the design document
            2. **Example**: save_content_to_blob('design_result.md', complete_design_content, container_name='{{container_name}}', folder_path='{{output_file_folder}}')
            3. **Content Requirements**: Include complete Azure architecture design, service mappings, migration strategy, and implementation roadmap
            4. **Verification**: After creation, verify with check_blob_exists('design_result.md', container_name='{{container_name}}', folder_path='{{output_file_folder}}')
            5. **NO TERMINATION**: Do not complete this step until the file is successfully created and verified

            **📋 REQUIRED RETURN STRUCTURE - EXACT FORMAT REQUIRED**:

            **🚨 CRITICAL: You MUST provide data in this EXACT format when terminating:**

            ```json
            {
                "result": "Success",
                "summary": "Complete architecture design summary here - be specific about what was designed",
                "azure_services": [
                    "Azure Kubernetes Service (AKS)",
                    "Azure Container Registry",
                    "Azure Key Vault",
                    "Azure Load Balancer",
                    "Azure Monitor",
                    "Azure Application Gateway"
                ],
                "architecture_decisions": [
                    "Selected AKS for container orchestration due to native Azure integration",
                    "Chose Azure Container Registry for secure image storage and distribution",
                    "Implemented Azure Key Vault for centralized secrets management",
                    "Configured Azure Load Balancer Standard for high availability"
                ],
                "outputs": [
                    {
                        "file": "{{output_file_folder}}/design_result.md",
                        "description": "Comprehensive Azure architecture design document"
                    }
                ]
            }
            ```

            **📋 ALTERNATIVE: If you CANNOT complete the design due to missing data:**

            ```json
            {
                "result": "Success",
                "summary": "Partial design completed - missing critical source data prevents full architecture design",
                "azure_services": ["Azure Kubernetes Service (AKS)"],
                "architecture_decisions": ["Selected AKS as primary container platform based on available analysis"],
                "outputs": [
                    {
                        "file": "{{output_file_folder}}/design_result.md",
                        "description": "Partial design document - requires additional analysis"
                    }
                ],
                "incomplete_reason": "Missing critical source platform analysis - verified using MCP tools: check_blob_exists('analysis_result.md') returned false",
                "missing_information": [
                    "Source platform analysis file (analysis_result.md)",
                    "Configuration file details",
                    "Platform complexity assessment"
                ]
            }
            ```

            **🛑 TERMINATION RULES - READ CAREFULLY**:

            1. **ALWAYS** provide the exact JSON structure above
            2. **ALWAYS** fill in result, summary, azure_services, architecture_decisions, outputs
            3. **NEVER** leave these fields empty or null
            4. **IF** you cannot complete full design, use incomplete_reason and missing_information
            5. **VERIFY** you created design_result.md file using save_content_to_blob BEFORE terminating
            6. **IF** file creation fails, use incomplete_reason to explain why

            **🔧 REASONING SUPPORT FOR PARTIAL COMPLETION**:
            **🚨 ANTI-HALLUCINATION: REASONING MUST BE EVIDENCE-BASED**

            When you cannot complete full design due to missing information or constraints:

            **BEFORE using incomplete_reason or missing_information, you MUST:**
            1. **VERIFY WITH MCP TOOLS**: Use check_blob_exists(), list_blobs_in_container(), read_blob_content()
            2. **DOCUMENT ACTUAL TOOL RESULTS**: Paste the actual MCP function outputs as evidence
            3. **ATTEMPT MULTIPLE APPROACHES**: Try different container paths, file names, folders
            4. **PROVIDE CONCRETE EVIDENCE**: No generic reasoning without tool verification

            **ACCEPTABLE REASONING PATTERNS** (with evidence):
            ✅ "Used check_blob_exists('analysis_result.md') returned: False - file missing"
            ✅ "Called list_blobs_in_container('processes', 'source') returned: empty folder"
            ✅ "Attempted read_blob_content('config.yaml') got error: file not found"

            **FORBIDDEN REASONING PATTERNS** (hallucination):
            ❌ "Complex networking configurations require investigation" (without attempting)
            ❌ "Advanced security settings need deeper analysis" (without checking)
            ❌ "Insufficient details available" (without using available tools)

            **REASONING FIELDS**:
            - **USE incomplete_reason**: Provide clear explanation WITH MCP tool evidence
            - **USE missing_information**: List specific data WITH verification attempts
            - **PARTIAL ARRAYS OK**: Empty/minimal azure_services, architecture_decisions, outputs acceptable WITH evidence
            - **STILL CREATE FILES**: Always attempt to create design_result.md with available information

            **🎯 QUALITY STANDARDS**:
            - Address all {{files_count}} analyzed configuration files
            - Provide {{platform_detected}}-specific Azure optimizations
            - Create implementation plan for {{overall_complexity}} complexity scenarios
            - Generate actionable insights for {{migration_type}} success
            - **MANDATORY**: Create and save design_result.md file using MCP blob service
            - **VERIFY**: Confirm file exists before claiming completion
            - **EVIDENCE-BASED REASONING**: Only use reasoning fields with MCP tool verification evidence
            - **NO HALLUCINATION**: Never provide generic reasoning without attempting available data access
            """

            # Using Template and replace values with comprehensive parameters
            jinja_template = Template(design_task)
            rendered_task = jinja_template.render(
                # Core parameters
                process_id=process_id,
                source_file_folder=parameters["source_file_folder"],
                workspace_file_folder=parameters["workspace_file_folder"],
                output_file_folder=parameters["output_file_folder"],
                container_name=parameters["container_name"],
                # Analysis-derived parameters
                migration_type=parameters["migration_type"],
                platform_detected=parameters["platform_detected"],
                confidence_score=parameters["confidence_score"],
                target_platform=parameters["target_platform"],
                files_count=parameters["files_count"],
                files_discovered=parameters["files_discovered"],
                overall_complexity=parameters["overall_complexity"],
                # Complexity analysis - handle both dict and Pydantic model forms
                network_complexity=parameters["complexity_analysis"].network_complexity,
                security_complexity=parameters[
                    "complexity_analysis"
                ].security_complexity,
                storage_complexity=parameters["complexity_analysis"].storage_complexity,
                compute_complexity=parameters["complexity_analysis"].compute_complexity,
            )
            # Run the orchestration with the rendered task

            runtime = InProcessRuntime()
            runtime.start()

            try:
                # Track orchestration start
                if self.telemetry:
                    await self.telemetry.update_agent_activity(
                        process_id,
                        "Conversation_Manager",
                        "expert_collaboration_starting",
                        "Starting expert design discussion with specialist agents",
                    )

                    # NEW: Use comprehensive timing infrastructure
                    # State is guaranteed to be DesignStepState (initialized in start_design_from_analysis)
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
                        f"Expert discussion initiated for process {process_id} analyzing design for {len(parameters.get('files_discovered', []))} files",
                    )

                # Initialize orchestration_result to None before the try block
                orchestration_result = None

                # Run the orchestration using the orchestrator
                if self.telemetry:
                    try:
                        await self.telemetry.update_agent_activity(
                            process_id,
                            "Conversation_Manager",
                            "experts_collaborating",
                            "Expert collaboration in progress - Azure Expert, Technical Architect, and platform experts working together",
                        )

                        orchestration_result = await self._orchestrator.invoke(
                            task=rendered_task, runtime=runtime
                        )

                        # Track successful orchestration invocation
                        await self.telemetry.update_agent_activity(
                            process_id,
                            "Conversation_Manager",
                            "expert_collaboration_invoked",
                            "Expert design discussion invocation completed successfully",
                        )
                    except Exception as e:
                        # Track orchestration failure
                        await self.telemetry.update_agent_activity(
                            process_id,
                            "Conversation_Manager",
                            "expert_collaboration_failed",
                            f"Expert design discussion failed during invocation: {str(e)}",
                        )
                        raise

                    # Get Design Result from orchestration result
                    try:
                        if self.telemetry:
                            await self.telemetry.update_agent_activity(
                                process_id,
                                "Conversation_Manager",
                                "expert_result_processing",
                                "Processing expert design discussion results",
                            )
                            if orchestration_result:
                                _ = await orchestration_result.get()

                            await self.telemetry.update_agent_activity(
                                process_id,
                                "Conversation_Manager",
                                "expert_result_retrieved",
                                "Expert design results successfully retrieved from discussion",
                            )
                    except Exception as e:
                        await self.telemetry.update_agent_activity(
                            process_id,
                            "Conversation_Manager",
                            "expert_result_processing_failed",
                            f"Failed to retrieve expert design results: {str(e)}",
                        )
                        raise

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

                ##############################################################
                # Make a result file
                ##############################################################
                # Add detailed debugging for orchestrator state

                # Add null safety checks for critical objects
                if not self._orchestrator or not self._orchestrator._manager:
                    logger.error(
                        "[FAILED] Orchestrator or manager is None - cannot retrieve design results"
                    )
                    raise RuntimeError(
                        "Orchestrator or manager not properly initialized"
                    )

                design_output = self._orchestrator._manager.final_termination_result  # type: ignore

                if design_output is None:
                    logger.error(
                        "[FAILED] Design output is None - orchestration may have failed"
                    )
                    raise RuntimeError("Design orchestration failed to produce results")

                if design_output.is_hard_terminated:
                    # SCENARIO 1: Hard termination -> PERMANENT FAILURE (using new pattern)
                    logger.info(
                        "[PERMANENT_FAILURE] Hard termination detected - processing as permanent failure"
                    )
                    await self._process_hard_termination_as_failure(design_output, process_id)
                else:
                    # Happy path: soft termination = successful completion
                    await self.telemetry.update_agent_activity(
                        process_id,
                        "Conversation_Manager",
                        "expert_result_validation_started",
                        "Starting validation of expert design discussion results",
                    )

                    # Validate that we have COMPLETE termination_output for successful completion
                    if design_output.termination_output is None:
                        await self.telemetry.update_agent_activity(
                            process_id,
                            "Conversation_Manager",
                            "expert_validation_failed",
                            "Expert design discussion completed successfully but termination_output is None - experts did not provide required data structure",
                        )
                        logger.error(
                            "[FAILED] Design completed but termination_output is None - agents did not follow required format"
                        )

                        # Create a clear failure explanation for telemetry
                        failure_explanation = (
                            "Design agents completed but failed to provide the required termination structure. "
                            "This indicates the agents did not follow the specified JSON format requirements. "
                            "Check agent prompts and ensure they understand the exact format needed."
                        )

                        await self.telemetry.update_agent_activity(
                            process_id,
                            "Conversation_Manager",
                            "expert_format_failure",
                            failure_explanation,
                        )

                        raise RuntimeError(
                            "Design agents failed to provide required termination structure. "
                            "Agents must provide: result, summary, azure_services, architecture_decisions, outputs. "
                            "Check agent prompt compliance and JSON format requirements."
                        )

                    # Enhanced validation with reasoning support
                    validation_errors = []
                    validation_warnings = []

                    # Check core required fields
                    if not design_output.termination_output.result:
                        validation_errors.append("result is missing or empty")
                    if not design_output.termination_output.summary:
                        validation_errors.append("summary is missing or empty")

                    # Check optional arrays with reasoning support
                    if not design_output.termination_output.azure_services:
                        if (
                            design_output.termination_output.incomplete_reason
                            or design_output.termination_output.missing_information
                        ):
                            validation_warnings.append(
                                "azure_services is empty but reasoning provided"
                            )
                        else:
                            validation_errors.append(
                                "azure_services is missing or empty array with no reasoning provided"
                            )

                    if not design_output.termination_output.architecture_decisions:
                        if (
                            design_output.termination_output.incomplete_reason
                            or design_output.termination_output.missing_information
                        ):
                            validation_warnings.append(
                                "architecture_decisions is empty but reasoning provided"
                            )
                        else:
                            validation_errors.append(
                                "architecture_decisions is missing or empty array with no reasoning provided"
                            )

                    if not design_output.termination_output.outputs:
                        if (
                            design_output.termination_output.incomplete_reason
                            or design_output.termination_output.missing_information
                        ):
                            validation_warnings.append(
                                "outputs is empty but reasoning provided"
                            )
                        else:
                            validation_errors.append(
                                "outputs is missing or empty array with no reasoning provided"
                            )

                    # If there are critical validation errors, fail with detailed explanation
                    if validation_errors:
                        validation_summary = f"Design termination_output validation failed: {', '.join(validation_errors)}"

                        await self.telemetry.update_agent_activity(
                            process_id,
                            "Conversation_Manager",
                            "expert_validation_failed",
                            validation_summary,
                        )

                        # Create detailed failure explanation
                        detailed_explanation = (
                            f"Design agents completed but provided incomplete termination_output. "
                            f"Missing/empty fields: {', '.join(validation_errors)}. "
                            f"This suggests agents did not follow the required JSON format. "
                            f"Agents should use 'incomplete_reason' and 'missing_information' fields "
                            f"when they cannot complete certain sections due to missing data."
                        )

                        await self.telemetry.update_agent_activity(
                            process_id,
                            "Conversation_Manager",
                            "expert_validation_detail",
                            detailed_explanation,
                        )

                        logger.error(
                            "[FAILED] Design termination_output validation failed: %s",
                            ", ".join(validation_errors),
                        )

                        raise RuntimeError(
                            f"Design agents provided incomplete termination_output. "
                            f"Missing/empty fields: {', '.join(validation_errors)}. "
                            f"Agents must provide all required fields or use reasoning fields "
                            f"(incomplete_reason, missing_information) to explain why sections cannot be completed. "
                            f"Check agent prompt compliance and JSON format requirements."
                        )

                    # Log warnings for incomplete but reasoned sections
                    if validation_warnings:
                        await self.telemetry.update_agent_activity(
                            process_id,
                            "Conversation_Manager",
                            "expert_validation_warnings",
                            f"Expert design discussion completed with reasoning for incomplete sections: {', '.join(validation_warnings)}",
                        )
                        logger.warning(
                            "[WARNING] Design completed with reasoning: %s",
                            ", ".join(validation_warnings),
                        )

                        # Log the reasoning provided
                        if design_output.termination_output.incomplete_reason:
                            logger.info(
                                "[REASONING] Design incomplete reason: %s",
                                design_output.termination_output.incomplete_reason,
                            )
                        if design_output.termination_output.missing_information:
                            logger.info(
                                "[REASONING] Missing information: %s",
                                ", ".join(
                                    design_output.termination_output.missing_information
                                ),
                            )

                    # Anti-hallucination validation for reasoning quality
                    if (
                        design_output.termination_output.incomplete_reason
                        or design_output.termination_output.missing_information
                    ):
                        await self._validate_reasoning_quality(
                            design_output.termination_output
                        )

                    # Validation successful (with or without warnings)
                    services_count = (
                        len(design_output.termination_output.azure_services)
                        if design_output.termination_output.azure_services
                        else 0
                    )
                    decisions_count = (
                        len(design_output.termination_output.architecture_decisions)
                        if design_output.termination_output.architecture_decisions
                        else 0
                    )
                    outputs_count = (
                        len(design_output.termination_output.outputs)
                        if design_output.termination_output.outputs
                        else 0
                    )

                    await self.telemetry.update_agent_activity(
                        process_id,
                        "Conversation_Manager",
                        "expert_validation_passed",
                        f"Expert design validation passed: result, summary, azure_services ({services_count} services), architecture_decisions ({decisions_count} decisions), outputs ({outputs_count} files){' - with reasoning for incomplete sections' if validation_warnings else ''}",
                    )

                    # Track successful completion
                    await self.telemetry.update_agent_activity(
                        process_id,
                        "Conversation_Manager",
                        "expert_step_completed_successfully",
                        f"Expert design discussion completed successfully with {len(design_output.termination_output.azure_services)} Azure services and {len(design_output.termination_output.architecture_decisions)} architecture decisions",
                    )

                    # Track successful orchestration
                    if self.telemetry:
                        await self.telemetry.update_agent_activity(
                            "Conversation_Manager",
                            "expert_collaboration_completed",
                            f"Expert design discussion completed successfully in {orchestration_duration:.2f} seconds",
                        )

                    # Create structured result
                    result = {
                        "process_id": process_id,
                        "workspace_file_folder": parameters["workspace_file_folder"],
                        "output_file_folder": parameters["output_file_folder"],
                        "container_name": parameters["container_name"],
                        "result_file_name": "design_result.md",
                        "state": design_output,
                        "execution_time_seconds": orchestration_duration,
                    }

                    # Invoke Event Sink - Task Recording
                    await context.emit_event(
                        process_event="OnStateChange",
                        data=result,
                    )

                    safe_log(
                        logger,
                        "info",
                        "[SUCCESS] Group chat design completed for process {process_id} in {duration} seconds",
                        process_id=process_id,
                        duration=f"{orchestration_duration:.2f}",
                    )

                    # Track step completion
                    if self.telemetry:
                        await self.telemetry.update_agent_activity(
                            "Conversation_Manager",
                            "expert_step_completed",
                            f"Expert design discussion completed for process {process_id} in {orchestration_duration:.2f} seconds",
                        )

                    #################################################
                    # Make up State Values
                    #################################################

                    # name: str = Field(default="DesignStepState", description="Name of the step state")
                    # version: str = Field(default="1.0", description="Version of the step state")
                    # reason: str = Field(default="", description="Reason for failure if any")
                    # architecture_created: list[str] = []
                    # recommendations: list[str] = []
                    # design_completed: bool = False
                    # final_result: Design_ExtendedBooleanResult | None = None
                    # result: bool = False

                    self._ensure_state_initialized()
                    assert self.state is not None  # For type checker
                    self.state.name = "DesignStepState"
                    self.state.version = "1.0"
                    self.state.reason = design_output.reason
                    self.state.architecture_created = (
                        design_output.termination_output.azure_services
                        if design_output.termination_output.azure_services
                        else []
                    )
                    self.state.recommendations = (
                        design_output.termination_output.architecture_decisions
                        if design_output.termination_output.architecture_decisions
                        else []
                    )
                    self.state.design_completed = True
                    self.state.final_result = design_output
                    self.state.result = True

                    # NEW: Set execution end time for comprehensive timing
                    # State is guaranteed to be DesignStepState (initialized above)
                    self.state.set_execution_end()
                    timing_summary = self.state.get_timing_summary()
                    logger.info(
                        f"[TIMING] Design completed - Total execution: {self.state.total_execution_duration:.2f}s"
                    )
                    logger.info(f"[TIMING] Timing summary: {timing_summary}")

                    # Track successful orchestration
                    await self.telemetry.update_agent_activity(
                        process_id,
                        "Conversation_Manager",
                        "design_discussion_complete",
                        f"Expert discussion completed successfully in {self.state.orchestration_duration or orchestration_duration:.2f} seconds",
                    )

                    # Emit success event - proper event handling
                    await context.emit_event(
                        process_event="DesignCompleted",
                        data={
                            "process_id": context_data.get("process_id"),
                            "analysis_result": context_data.get("analysis_result"),
                            "design_result": result,
                            "app_context": context_data.get("app_context"),
                        },
                    )

            finally:
                # Always clean up runtime
                await runtime.stop_when_idle()
                logger.info("[CLEANUP] Design runtime cleaned up")
        except Exception as e:
            # ORCHESTRATION-LEVEL ERROR HANDLING - Different timing context than setup errors
            logger.error(
                f"[ORCHESTRATION FAILURE] Exception during orchestration phase: {str(e)}"
            )

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
            #         step_name="DesignStep",
            #         process_id=process_id,
            #         context_data=context_data,
            #         step_start_time=self.state.execution_start_time,
            #         step_phase="execute_design_orchestration",
            #     )

            #     # Set state for migration service to read - PRIMARY failure indicator
            #     self.state.result = False
            #     self.state.reason = f"Retryable infrastructure error: {error_message}"
            #     self.state.failure_context = (
            #         await failure_collector.create_step_failure_state(
            #             reason=f"Infrastructure error (retryable): {error_message}",
            #             execution_time=time_to_failure,
            #             files_attempted=self.state.architecture_created,
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
            # NOTE: This is orchestration failure - capture timing
            self.state.set_execution_end()

            # Calculate time to failure (setup + error handling time)
            time_to_failure = self.state.total_execution_duration or 0.0

            # Collect system failure context with full stack trace
            failure_collector = StepFailureCollector()
            system_context = await failure_collector.collect_system_failure_context(
                error=e,
                step_name="DesignStep",
                process_id=process_id,
                context_data=context_data,
                step_start_time=self.state.execution_start_time,
                step_phase="execute_design_orchestration",
            )

            # Set state for migration service to read - PRIMARY failure indicator
            self.state.result = False
            self.state.reason = f"Orchestration failed: {error_message}"
            self.state.failure_context = (
                await failure_collector.create_step_failure_state(
                    reason=f"Design failed: {error_message}",
                    execution_time=time_to_failure,
                    files_attempted=self.state.architecture_created,
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
                f"[ORCHESTRATION FAILURE] State updated with failure context - total time: {time_to_failure:.2f}s in design"
            )

            # Don't re-raise - let migration service read the failure context
            return
        finally:
            logger.info("[SUCCESS] Design step execution completed")
