"""
Documentation Step - Single responsibility: Generate final migration reports.

Following SK Process Framework best practices:
- Single responsibility principle
- Proper event handling with error management
- Isolated kernel instance
- Clear input/output via events
- Step-specific group chat orchestration
"""

import logging
import time
from typing import TYPE_CHECKING, Any

from jinja2 import Template
from pydantic import Field
from semantic_kernel.agents import GroupChatOrchestration
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
from libs.steps.orchestration.documentation_orchestration import (
    DocumentationOrchestrator,
)
from libs.steps.orchestration.models.documentation_result import (
    AggregatedResults,
    Documentation_ExtendedBooleanResult,
)
from libs.steps.step_failure_collector import StepFailureCollector
from plugins.mcp_server import MCPBlobIOPlugin, MCPDatetimePlugin, MCPMicrosoftDocs
from utils.agent_telemetry import TelemetryManager
from utils.logging_utils import create_migration_logger, safe_log
from utils.mcp_context import PluginContext, with_name
from utils.tool_tracking import ToolTrackingMixin

logger = create_migration_logger(__name__)


class DocumentationStepState(BaseStepState):
    """State for the Documentation step following best practices."""

    # Base fields required by KernelProcessStepState
    name: str = Field(
        default="DocumentationStepState", description="Name of the step state"
    )
    version: str = Field(default="1.0", description="Version of the step state")
    result: bool | None = None  # None = not started, True = success, False = failed
    documentation_generated: str = ""
    reports: AggregatedResults | None = None
    documentation_completed: bool = False
    final_result: Documentation_ExtendedBooleanResult | None = None
    reason: str = Field(default="", description="Reason for failure if any")

    requires_immediate_retry: bool = Field(default=False)
    termination_details: dict[str, Any] | None = Field(default=None)


class DocumentationStep(KernelProcessStep[DocumentationStepState], ToolTrackingMixin):
    """
    Documentation step that generates final migration reports.

    Following SK Process Framework best practices:
    - Single responsibility: documentation generation only
    - Isolated kernel instance to prevent recursive invocation
    - Proper error handling and event emission
    - Simple, focused functionality
    """

    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}

    state: DocumentationStepState | None = Field(
        default_factory=lambda: DocumentationStepState(
            name="DocumentationStepState", version="1.0"
        )
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
        if self._kernel_agent is None:
            raise RuntimeError("Kernel agent not initialized")

        return PluginContext(
            kernel_agent=self._kernel_agent,
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
            "[TOOLS] DOCUMENTATION STEP CONSTRUCTOR: Starting synchronous initialization..."
        )
        self._kernel_agent = None
        self._orchestrator: GroupChatOrchestration | None = None

        # No shared MCP context - this step creates its own

        logger.info(
            "[SUCCESS] DOCUMENTATION STEP CONSTRUCTOR: Synchronous initialization complete"
        )

    async def activate(self, state: KernelProcessStepState[DocumentationStepState]):
        """
        Activate the step for state initialization only.

        Note: Kernel agent creation moved to start_documentation_from_yaml() for lazy initialization.
        This avoids unnecessary resource allocation for steps that may never execute.
        """
        self.state = state.state
        # Ensure state is never None
        if self.state is None:
            self.state = DocumentationStepState(
                name="DocumentationStepState", version="1.0"
            )

        logger.info(
            "[SUCCESS] DOCUMENTATION STEP ACTIVATE: Step state initialized (kernel agent will be created when needed)"
        )

    def _ensure_state_initialized(self) -> None:
        """Ensure state is properly initialized before use."""
        if self.state is None:
            self.state = DocumentationStepState(
                name="DocumentationStepState", version="1.0"
            )

    def _extract_comprehensive_step_parameters(
        self, context_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Extract comprehensive parameters from context data including previous step results.

        Documentation step receives YAML step results in context_data structure:
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
            },
            "yaml_result": {
                "state": Yaml_ExtendedBooleanResult {
                    "termination_output": YamlOutput {...}
                }
            }
        }
        """
        # Basic parameters
        yaml_result = context_data.get("yaml_result")
        analysis_result = context_data.get("analysis_result")
        design_result = context_data.get("design_result")

        # Handle None results gracefully - this is the core issue we're fixing
        if yaml_result is None:
            logger.warning("yaml_result is None - YAML step may have failed")
            yaml_result = {}
        if analysis_result is None:
            logger.warning("analysis_result is None - Analysis step may have failed")
            analysis_result = {}
        if design_result is None:
            logger.warning("design_result is None - Design step may have failed")
            design_result = {}

        # Helper functions to safely extract state data
        def safe_get_state(result_dict):
            """Safely get state from result dict."""
            if not result_dict:
                return None
            return result_dict.get("state")

        def safe_get_termination_output(state):
            """Safely get termination_output from state."""
            if state is None:
                return None
            if hasattr(state, "termination_output"):
                return state.termination_output
            if isinstance(state, dict):
                return state.get("termination_output")
            return None

        # Extract states safely
        yaml_state = safe_get_state(yaml_result)
        analysis_state = safe_get_state(analysis_result)
        design_state = safe_get_state(design_result)

        # Extract termination outputs safely
        yaml_output = safe_get_termination_output(yaml_state)
        analysis_output = safe_get_termination_output(analysis_state)
        design_output = safe_get_termination_output(design_state)

        # Build comprehensive parameter set for enhanced documentation using safely extracted data
        parameters = {
            # Basic process parameters
            "process_id": context_data.get("process_id", "default-process-id"),
            "source_file_folder": yaml_result.get("source_file_folder", "source"),
            "output_file_folder": yaml_result.get("output_file_folder", "converted"),
            "workspace_file_folder": yaml_result.get(
                "workspace_file_folder", "workspace"
            ),
            "container_name": yaml_result.get("container_name", "processes"),
            # Safely extracted data - using our helper functions
            "total_files_analyzed": len(
                analysis_output.files_discovered
                if analysis_output and hasattr(analysis_output, "files_discovered")
                else []
            ),
            "analyzed_files": (
                analysis_output.files_discovered
                if analysis_output and hasattr(analysis_output, "files_discovered")
                else []
            ),
            "yaml_files_created": (
                yaml_output.converted_files
                if yaml_output and hasattr(yaml_output, "converted_files")
                else []
            ),
            "migration_readiness_score": (
                analysis_output.migration_readiness
                if analysis_output and hasattr(analysis_output, "migration_readiness")
                else "Not Available"
            ),
            "overall_conversion_accuracy": (
                yaml_output.overall_conversion_metrics.overall_accuracy
                if yaml_output
                and hasattr(yaml_output, "overall_conversion_metrics")
                and hasattr(yaml_output.overall_conversion_metrics, "overall_accuracy")
                else "Not Available"
            ),
            "azure_compatibility_score": (
                yaml_output.overall_conversion_metrics.azure_compatibility
                if yaml_output
                and hasattr(yaml_output, "overall_conversion_metrics")
                and hasattr(
                    yaml_output.overall_conversion_metrics, "azure_compatibility"
                )
                else "Not Available"
            ),
            # Additional safely extracted fields
            "azure_conversion_summary": (
                yaml_output.summary
                if yaml_output and hasattr(yaml_output, "summary")
                else "No summary available"
            ),
            "yaml_conversion_status": (
                yaml_output.overall_conversion_metrics
                if yaml_output and hasattr(yaml_output, "overall_conversion_metrics")
                else {}
            ),
            "total_yaml_files": (
                yaml_output.converted_files
                if yaml_output and hasattr(yaml_output, "converted_files")
                else []
            ),
            "total_files_converted": (
                len(yaml_output.converted_files)
                if yaml_output
                and hasattr(yaml_output, "converted_files")
                and yaml_output.converted_files
                and isinstance(yaml_output.converted_files, list)
                else 0
            ),
            "conversion_quality": (
                yaml_output.conversion_quality
                if yaml_output and hasattr(yaml_output, "conversion_quality")
                else {}
            ),
            "conversion_report": (
                yaml_output.conversion_report_file
                if yaml_output and hasattr(yaml_output, "conversion_report_file")
                else "No conversion report available"
            ),
            "total_expert_insights": (
                yaml_output.expert_insights
                if yaml_output and hasattr(yaml_output, "expert_insights")
                else []
            ),
            "source_platform": (
                analysis_output.platform_detected
                if analysis_output and hasattr(analysis_output, "platform_detected")
                else "Unknown"
            ),
            "target_platform": "Azure AKS",
            "platform_confidence": (
                analysis_output.confidence_score
                if analysis_output and hasattr(analysis_output, "confidence_score")
                else "Not Available"
            ),
            # Architecture context (if preserved from design step)
            "azure_services_used": (
                design_output.azure_services
                if design_output and hasattr(design_output, "azure_services")
                else []
            ),
            "architecture_summary": (
                design_output.summary
                if design_output and hasattr(design_output, "summary")
                else "No architecture summary available"
            ),
            # Full data access for advanced scenarios
            "full_yaml_data": yaml_output,
            "full_analysis_data": analysis_result,
            "full_design_data": design_result,
            "architecture_decisions": (
                design_output.architecture_decisions
                if design_output and hasattr(design_output, "architecture_decisions")
                else []
            ),
            "migration_concerns": (
                analysis_output.migration_readiness.concerns
                if analysis_output
                and hasattr(analysis_output, "migration_readiness")
                and hasattr(analysis_output.migration_readiness, "concerns")
                else []
            ),
            "migration_recommendations": (
                analysis_output.migration_readiness.recommendations
                if analysis_output
                and hasattr(analysis_output, "migration_readiness")
                and hasattr(analysis_output.migration_readiness, "recommendations")
                else []
            ),
            "complexity_analysis": (
                analysis_output.complexity_analysis
                if analysis_output and hasattr(analysis_output, "complexity_analysis")
                else "Not Available"
            ),
            "overall_migration_success": (
                yaml_output.overall_conversion_metrics.overall_accuracy
                if yaml_output
                and hasattr(yaml_output, "overall_conversion_metrics")
                and hasattr(yaml_output.overall_conversion_metrics, "overall_accuracy")
                else "Not Available"
            ),
            "steps_completed": ["analysis", "design", "yaml"],
            "total_execution_time": sum(
                [
                    (
                        analysis_state.execution_time_seconds
                        if analysis_state
                        and hasattr(analysis_state, "execution_time_seconds")
                        else 0
                    ),
                    (
                        design_state.execution_time_seconds
                        if design_state
                        and hasattr(design_state, "execution_time_seconds")
                        else 0
                    ),
                    (
                        yaml_state.execution_time_seconds
                        if yaml_state and hasattr(yaml_state, "execution_time_seconds")
                        else 0
                    ),
                ]
            ),
            "analysis_expert_insights": (
                analysis_output.expert_insights
                if analysis_output and hasattr(analysis_output, "expert_insights")
                else []
            ),
            "yaml_expert_insights": (
                yaml_output.expert_insights
                if yaml_output and hasattr(yaml_output, "expert_insights")
                else []
            ),
        }

        return parameters

    def _create_termination_context_data(self, document_output) -> dict[str, Any]:
        """Create context data for termination failure scenarios"""
        context_data = {
            "termination_type": document_output.termination_type,
            "termination_reason": document_output.reason,
            "blocking_issues": list(document_output.blocking_issues) if document_output.blocking_issues else [],
        }

        # Add termination output details if available
        if document_output.termination_output:
            context_data.update({
                "aggregated_results": document_output.termination_output.aggregated_results or {},
                "expert_insights": document_output.termination_output.expert_insights or [],
                "documentation_summary": document_output.termination_output.documentation_summary or {},
            })

        return context_data

    async def _process_hard_termination_as_failure(
        self, document_output, process_id: str
    ) -> None:
        """Process ALL hard terminations as permanent failures using existing error infrastructure"""
        # Extract reports safely
        reports = (
            document_output.termination_output.aggregated_results
            if document_output.termination_output and hasattr(document_output.termination_output, 'aggregated_results')
            else {}
        )

        # Step 1: Update telemetry with failure notification
        await self.telemetry.update_agent_activity(
            process_id,
            "Conversation_Manager",
            "documentation_permanently_failed",
            f"Documentation failed permanently due to {document_output.termination_type}: {document_output.reason}. Expert consensus: {document_output.blocking_issues}"
        )

        # Step 2: Create failure context using existing StepFailureCollector
        # Create "virtual exception" for termination scenario
        termination_error = ValueError(f"Hard termination: {document_output.termination_type} - {document_output.reason}")

        # Use existing StepFailureCollector
        failure_collector = StepFailureCollector()
        system_context = await failure_collector.collect_system_failure_context(
            error=termination_error,
            step_name="DocumentationStep",
            process_id=process_id,
            context_data=self._create_termination_context_data(document_output),
            step_start_time=self.state.execution_start_time,
            step_phase="hard_termination_documentation"
        )

        # Step 3: Set failure state (NOT retry state)
        self._ensure_state_initialized()
        assert self.state is not None  # For type checker

        # Set up basic state (similar to current logic but as FAILURE)
        self.state.name = "DocumentationStepState"
        self.state.id = "Documentation"
        self.state.version = "1.0"
        self.state.result = False  # FAILURE, not retry
        self.state.documentation_completed = False
        self.state.reports = reports
        self.state.documentation_generated = ""
        self.state.final_result = document_output
        self.state.reason = f"Hard termination: {document_output.termination_type} - {document_output.reason}"

        # Set failure context using existing infrastructure
        self.state.failure_context = await failure_collector.create_step_failure_state(
            reason=f"Documentation terminated: {document_output.termination_type} - {document_output.reason}",
            execution_time=self.state.total_execution_duration or 0.0,
            files_attempted=[],  # Documentation doesn't process files directly
            system_failure_context=system_context
        )

        # CRITICAL: Do NOT set retry flags
        # self.state.requires_immediate_retry = False (default)
        # No termination_details for retry

        # Step 4: Record failure outcome in telemetry
        failure_details = {
            "termination_type": document_output.termination_type,
            "termination_reason": document_output.reason,
            "blocking_issues": document_output.blocking_issues,
            "reports_generated": len(reports) if isinstance(reports, dict) else 0,
            "handled_as": "permanent_failure"
        }

        await self.telemetry.update_agent_activity(
            process_id,
            "Documentation_Expert",
            "step_permanently_failed",
            f"Documentation step terminated permanently: {failure_details}"
        )

    @kernel_function(description="Handle documentation event from YAML completion")
    async def start_documentation_from_yaml(
        self, context: KernelProcessStepContext, context_data: dict[str, Any]
    ) -> None:
        """
        Handle the YamlCompleted event and delegate to execute_documentation.

        This function extracts parameters from the context_data and calls execute_documentation.
        Each step creates its own PluginContext for clean isolation.
        """
        # Initialize state and execution timing following gold standard pattern
        self._ensure_state_initialized()

        # Start execution timing using BaseStepState infrastructure
        if self.state:
            self.state.set_execution_start()

        # Extract process_id for telemetry tracking
        process_id = context_data.get("process_id", "default-process-id")
        app_context = context_data.get("app_context")
        self.telemetry = TelemetryManager(app_context)

        try:
            logger.info(
                "[START] Received YamlCompleted event, starting documentation with lazy kernel agent initialization..."
            )

            # Lazy initialization: Create kernel agent only when step actually needs to execute
            if self._kernel_agent is None:
                logger.info(
                    "[TOOLS] DOCUMENTATION STEP: Creating kernel agent for execution..."
                )
                self._kernel_agent = semantic_kernel_agent(
                    env_file_path=None,  # Do not load .env file
                    custom_service_prefixes=None,
                    use_entra_id=True,
                )
                logger.info(
                    "[TOOLS] DOCUMENTATION STEP: About to initialize kernel agent..."
                )
                await self._kernel_agent.initialize_async()
                logger.info(
                    "[SUCCESS] DOCUMENTATION STEP: Kernel agent ready for execution"
                )

            # Transition to Documentation phase
            if self.telemetry:
                await self.telemetry.transition_to_phase(
                    process_id=process_id, phase="Documentation", step="Documentation"
                )
                await self.telemetry.update_agent_activity(
                    process_id=process_id,
                    agent_name="Conversation_Manager",
                    action="expert_documentation_starting",
                    message_preview="Starting expert documentation generation discussion",
                )

            # Initialize step-level telemetry - moved here as this is when step actually starts
            await self.telemetry.update_agent_activity(
                process_id=process_id,
                agent_name="Conversation_Manager",
                action="expert_step_initializing",
                message_preview=f"Expert documentation discussion starting for process {process_id}",
            )

            # Update agent activity with instance telemetry if available
            await self.telemetry.update_agent_activity(
                process_id=process_id,
                agent_name="Conversation_Manager",
                action="expert_step_starting",
                message_preview="Starting expert documentation generation discussion for migration reports",
            )

            # Extract parameters from context_data
            process_id = context_data.get("process_id", "default-process-id")
            yaml_result = context_data.get("yaml_result", {})
            source_file_folder = yaml_result.get("source_file_folder", "source")
            output_file_folder = yaml_result.get("output_file_folder", "converted")

            async def agent_response_callback(message: ChatMessageContent):
                # Handle agent responses specific to the documentation step
                try:
                    agent_name = getattr(message, "name", "Unknown_Agent")
                    content = getattr(message, "content", "No content")

                    print(f"📝 [DOCUMENTATION CALLBACK] Agent: {agent_name}")
                    print(f"📝 [DOCUMENTATION CALLBACK] Content: {content[:200]}...")

                    # Enhanced tool usage detection and tracking
                    await self.detect_and_track_tool_usage(
                        process_id, agent_name, content
                    )

                    # Also log to telemetry if available
                    await self.telemetry.update_agent_activity(
                        process_id=process_id,
                        agent_name=agent_name,
                        action="documentation_response",
                        message_preview=f"Documentation phase response: {content[:200]}...",
                    )
                except Exception as e:
                    print(f"⚠️ [DOCUMENTATION CALLBACK ERROR] {e}")
                    # Continue execution even if callback fails

            async with self.create_task_local_mcp_context() as mcp_context:
                # Create documentation orchestrator with proper agent setup using step's MCP context
                documentation_orchestrator = DocumentationOrchestrator(
                    kernel_agent=self._kernel_agent, process_context=context_data
                )
                # Pass the step's MCP context to orchestrator instead of letting it create its own
                self._orchestrator = await documentation_orchestrator.create_documentation_orchestration_with_context(
                    mcp_context,
                    context_data,
                    agent_response_callback=agent_response_callback,
                    telemetry=self.telemetry,
                )

                logger.info(
                    f"[FOLDER] Documentation will process ({process_id}): {source_file_folder} -> {output_file_folder}"
                )

                # Execute documentation INSIDE the context manager to keep orchestrator valid
                await self.execute_documentation(
                    context=context, context_data=context_data
                )

        except Exception as e:
            # Get error info for telemetry (no redundant dictionary needed)
            error_type = type(e).__name__
            error_message = str(e)

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
                step_name="DocumentationStep",
                process_id=process_id,
                context_data=context_data,
                step_start_time=self.state.execution_start_time,
                step_phase="start_documentation_from_yaml",
            )

            # Set state for migration service to read - PRIMARY failure indicator
            self.state.result = False
            self.state.reason = f"Critical error: {error_message}"
            self.state.failure_context = (
                await failure_collector.create_step_failure_state(
                    reason=f"Documentation failed: {error_message}",
                    execution_time=time_to_failure,
                    files_attempted=0,  # Documentation doesn't process individual files
                    system_failure_context=system_context,
                )
            )

            await self.telemetry.update_agent_activity(
                process_id,
                "Conversation_Manager",
                "discussion_critical_error",
                f"Expert discussion encountered critical error - {error_type}: {error_message}",
            )

            logger.error(
                f"[CRITICAL] State updated with comprehensive failure context - time to failure: {time_to_failure:.2f}s (setup phase failure)"
            )

            # Don't re-raise - let migration service read the failure context from state
            return

    def _create_standard_documentation_task(self) -> str:
        """Create enhanced comprehensive migration documentation task template utilizing rich step data."""
        return """
        **🎯 COMPREHENSIVE MIGRATION DOCUMENTATION OBJECTIVE**: Generate professional migration report leveraging ALL step data

        **📊 MIGRATION OVERVIEW**:
        - Source Platform: {{source_platform}} (Confidence: {{platform_confidence}})
        - Migration Readiness Score: {{migration_readiness_score}}
        - Overall Migration Success: {{overall_migration_success}}
        - Steps Completed: {{steps_completed}}/3
        - Total Execution Time: {{total_execution_time}} seconds
        - Pipeline Version: {{pipeline_version}}

        **📁 FILE LOCATIONS & RESULTS**:
        - Analysis Results: {{output_file_folder}}/analysis_result.md
        - Design Results: {{output_file_folder}}/design_result.md
        - Conversion Results: {{output_file_folder}}/file_converting_result.md
        - Source folder: {{source_file_folder}}
        - Workspace folder: {{workspace_file_folder}}
        - Output folder: {{output_file_folder}}
        - Container: {{container_name}}

        **🔍 COMPREHENSIVE ANALYSIS DATA**:
        - **Platform Analysis**: {{source_platform}} detected with {{platform_confidence}} confidence
        - **Files Analyzed**: {{total_files_analyzed}} files discovered and analyzed
        - **Migration Readiness**: {{migration_readiness_score}} overall score
        - **Key Concerns**: {{migration_concerns_count}} concerns identified
        - **Recommendations**: {{migration_recommendations_count}} recommendations provided

        **📐 COMPLEXITY ASSESSMENT**:
        - **Network Complexity**: {{network_complexity}}
        - **Security Complexity**: {{security_complexity}}
        - **Storage Complexity**: {{storage_complexity}}
        - **Compute Complexity**: {{compute_complexity}}

        **🏗️ ARCHITECTURE DESIGN RESULTS**:
        - **Design Status**: {{design_result_status}}
        - **Azure Services Recommended**: {{azure_services_count}} services
        - **Key Azure Services**: {{primary_azure_services}}
        - **Architecture Decisions**: {{architecture_decisions_count}} decisions made
        - **Design Summary**: {{design_summary}}

        **⚙️ YAML CONVERSION RESULTS**:
        - **Files Converted**: {{total_files_converted}} files successfully converted
        - **Overall Accuracy**: {{overall_conversion_accuracy}}
        - **Azure Compatibility**: {{azure_compatibility_score}}
        - **Production Readiness**: {{production_readiness_status}}
        - **Security Hardening**: {{security_hardening_status}}
        - **Performance Optimization**: {{performance_optimization_status}}

        **📋 COMPREHENSIVE DELIVERABLES**:
        1. **Executive Summary**:
           - Migration readiness assessment with {{migration_readiness_score}} score
           - Overall conversion success with {{overall_conversion_accuracy}} accuracy
           - Key recommendations for leadership decision making
           - Risk assessment with {{migration_concerns_count}} concerns identified
           - Investment summary and timeline projections

        2. **Technical Platform Analysis**:
           - Complete {{source_platform}} platform analysis with {{platform_confidence}} confidence
           - Detailed file inventory of {{total_files_analyzed}} files with complexity ratings
           - Multi-dimensional complexity assessment across network, security, storage, and compute
           - Migration readiness breakdown with specific concerns and recommendations

        3. **Azure Architecture Design Documentation**:
           - Complete catalog of {{azure_services_count}} recommended Azure services with rationale
           - Detailed architecture decisions with {{architecture_decisions_count}} key decisions
           - Service mapping from {{source_platform}} components to Azure services
           - Scalability, cost, and operational considerations

        4. **YAML Conversion Analysis**:
           - File-by-file conversion results for {{total_files_converted}} files
           - Accuracy metrics with {{overall_conversion_accuracy}} overall accuracy
           - Azure compatibility assessment with {{azure_compatibility_score}} score
           - Multi-dimensional quality analysis with production readiness evaluation

        5. **Implementation Roadmap**:
           - Phase-based deployment strategy leveraging design decisions
           - Pre-deployment requirements and dependencies identification
           - Testing and validation approach with success criteria
           - Go-live checklist and rollback procedures

        6. **Expert Insights Synthesis**:
           - Aggregated insights from {{total_expert_insights}} expert recommendations
           - Cross-step analysis connecting analysis, design, and conversion phases
           - Best practices and lessons learned compilation
           - Platform-specific considerations and Azure optimization strategies

        **👥 EXPERT RESPONSIBILITIES WITH ENHANCED CONTEXT**:
        - **Chief Architect**: Create executive-ready assessment using {{migration_readiness_score}} readiness score, validate architectural consistency across {{architecture_decisions_count}} decisions
        - **{{source_platform}} Expert**: Document platform-specific insights from {{total_files_analyzed}} file analysis, address {{migration_concerns_count}} platform concerns
        - **Azure Expert**: Provide detailed guidance on {{azure_services_count}} Azure services, optimize configurations for {{overall_conversion_accuracy}} conversion accuracy
        - **Technical Writer**: Create professional documentation integrating {{total_expert_insights}} expert insights with clear structure and actionable recommendations

        **✅ SUCCESS CRITERIA WITH MEASURABLE OUTCOMES**:
        - Complete utilization of analysis data from {{total_files_analyzed}} files
        - Full integration of {{azure_services_count}} Azure service recommendations
        - Comprehensive conversion analysis of {{total_files_converted}} converted files
        - Executive-ready summary with {{migration_readiness_score}} readiness assessment
        - Technical implementation guide with {{architecture_decisions_count}} architectural decisions

        **📤 MANDATORY OUTPUT STRUCTURE**:
        - **migration_report.md** in {{output_file_folder}}
        - all participants should actively collaborate to co-author and edit the migration report
        - Ensure clarity, professionalism, and actionable insights through team collaboration
        - **COLLABORATIVE APPROACH**: Actively work together to create the best possible migration report
        - **CRITICAL**: Don't delete, modify, or clean up any existing files from previous steps (analysis, design, conversion results)
        - **READ-ONLY FOR PREVIOUS RESULTS**: Only read from existing previous step files for reference, never modify them
        - **ACTIVE EDITING FOR REPORT**: Actively create, edit, and improve the migration_report.md collaboratively

        **📋 REQUIRED COMPREHENSIVE REPORT STRUCTURE**:
        ```markdown
        # {{source_platform}} to Azure Migration Report

        ## Executive Summary
        - Migration Readiness: {{migration_readiness_score}}
        - Conversion Success: {{overall_conversion_accuracy}}
        - Azure Compatibility: {{azure_compatibility_score}}
        - Recommended Action: [PROCEED/REVIEW/MODIFY]

        ## Technical Analysis
        ### Source Platform Assessment
        - Platform: {{source_platform}} ({{platform_confidence}} confidence)
        - Files Analyzed: {{total_files_analyzed}}
        - Complexity Assessment: Multi-dimensional analysis

        ### Architecture Design
        - Azure Services: {{azure_services_count}} services recommended
        - Key Decisions: {{architecture_decisions_count}} architectural decisions
        - Design Status: {{design_result_status}}

        ### Conversion Results
        - Files Converted: {{total_files_converted}}
        - Overall Accuracy: {{overall_conversion_accuracy}}
        - Production Readiness: {{production_readiness_status}}

        ## Implementation Roadmap
        - Phase 1: Pre-deployment preparation
        - Phase 2: Core service migration
        - Phase 3: Validation and optimization
        - Phase 4: Go-live and monitoring

        ## Risk Assessment & Mitigation
        - Identified Concerns: {{migration_concerns_count}}
        - Mitigation Strategies: Detailed for each concern
        - Success Probability: Based on readiness assessment

        ## Expert Recommendations
        - Cross-phase insights from {{total_expert_insights}} expert inputs
        - Platform-specific guidance
        - Azure optimization strategies

        ## References
        - Microsoft Azure Documentation Links
        - Azure Well-Architected Framework References
        - Azure Kubernetes Service Official Documentation
        - Cited Configuration and Best Practice Guides
        ```

        **🎯 QUALITY STANDARDS**:
        - Use ALL available data from analysis, design, and conversion steps
        - Include specific metrics, percentages, and counts from actual results
        - **MANDATORY**: Include "## References" section with all Microsoft documentation citations
        - **CITATION FORMAT**: [Service/Topic Name](https://docs.microsoft.com/url) - Brief description
        - Provide actionable recommendations with clear priority levels
        - Maintain professional standards suitable for executive review
        - Ensure technical depth appropriate for implementation teams
        - Cross-reference all sections for consistency and completeness
        """

    async def execute_documentation(
        self,
        context: KernelProcessStepContext,
        context_data: dict[str, Any] | None = None,
    ) -> None:
        """
        Execute documentation following single responsibility principle.

        Enhanced to leverage comprehensive data from all previous steps.

        Responsibilities:
        - Extract rich data from analysis, design, and YAML steps
        - Orchestrate group chat for comprehensive documentation generation
        - Coordinate expert agents for detailed migration reporting
        - Emit appropriate events with results
        """
        # Initialize context data if None
        if not context_data:
            context_data = {}

        # Extract comprehensive step parameters for enhanced documentation
        step_parameters = self._extract_comprehensive_step_parameters(context_data)

        # Get process ID for telemetry tracking
        process_id = step_parameters["process_id"]

        # Start execution timing using BaseStepState infrastructure
        self._ensure_state_initialized()
        self.state.set_execution_start()

        # Track start of documentation execution with enhanced context
        await self.telemetry.update_agent_activity(
            process_id=process_id,
            agent_name="Conversation_Manager",
            action="expert_documentation_starting",
            message_preview=f"Beginning expert comprehensive migration documentation discussion for {step_parameters['source_platform']} -> Azure (Process: {process_id})",
        )

        try:
            logger.info(
                "[NOTES] Starting enhanced documentation phase leveraging comprehensive step data..."
            )
            logger.info(
                f"[CONTEXT] Platform: {step_parameters['source_platform']}, "
                f"Files: {step_parameters['total_files_analyzed']}, "
                f"Conversions: {step_parameters.get('total_files_converted', 0)}, "
                f"Accuracy: {step_parameters['overall_conversion_accuracy']}"
            )

            logger.info(
                "[TARGET] Starting comprehensive migration report generation..."
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
                    "[FAILED] Orchestrator not available - cannot perform documentation"
                )
                raise RuntimeError(
                    "Documentation orchestrator not initialized - critical failure"
                )

            # Detect error context and choose appropriate template
            is_error_documentation = context_data.get("error_analysis_required", False)
            documentation_type = context_data.get(
                "documentation_type", "comprehensive_migration_report"
            )

            if is_error_documentation or documentation_type == "error_analysis_report":
                # Use error-specific documentation template with incident response focus
                documentation_task = self._create_error_documentation_task()
                logger.info(
                    "[ERROR_DOC] Using error-specific documentation template with incident response capabilities"
                )
            else:
                # Use standard successful migration documentation template
                documentation_task = self._create_standard_documentation_task()
                logger.info(
                    "[STANDARD_DOC] Using standard migration documentation template"
                )

            # Using Template with comprehensive parameters for enhanced documentation
            jinja_template = Template(documentation_task)
            rendered_task = jinja_template.render(
                # Basic process parameters
                process_id=process_id,
                source_file_folder=source_file_folder,
                workspace_file_folder=workspace_file_folder,
                output_file_folder=output_file_folder,
                container_name=container_name,
                # Enhanced analysis parameters
                source_platform=step_parameters["source_platform"],
                platform_confidence=step_parameters["platform_confidence"],
                total_files_analyzed=step_parameters["total_files_analyzed"],
                analyzed_files=step_parameters["analyzed_files"],
                migration_readiness_score=step_parameters["migration_readiness_score"],
                migration_concerns_count=len(step_parameters["migration_concerns"]),
                migration_recommendations_count=len(
                    step_parameters["migration_recommendations"]
                ),
                # Complexity analysis parameters
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
                # Design parameters
                design_result_status=step_parameters["full_design_data"],
                azure_services_count=len(step_parameters["azure_services_used"]),
                primary_azure_services=", ".join(
                    step_parameters["azure_services_used"][:3]
                )
                if step_parameters["azure_services_used"]
                else "N/A",
                architecture_decisions_count=len(
                    step_parameters["architecture_decisions"]
                ),
                design_summary=step_parameters["architecture_summary"],
                # YAML conversion parameters
                total_files_converted=step_parameters.get("total_files_converted", 0),
                overall_conversion_accuracy=step_parameters[
                    "overall_conversion_accuracy"
                ],
                azure_compatibility_score=step_parameters["azure_compatibility_score"],
                production_readiness_status=step_parameters[
                    "conversion_quality"
                ].production_readiness,
                security_hardening_status=step_parameters[
                    "conversion_quality"
                ].security_hardening,
                performance_optimization_status=step_parameters[
                    "conversion_quality"
                ].performance_optimization,
                # Executive summary parameters
                overall_migration_success=step_parameters["overall_migration_success"],
                steps_completed=step_parameters["steps_completed"],
                total_execution_time=step_parameters["total_execution_time"],
                pipeline_version="1.0",
                # Expert insights parameters
                total_expert_insights=len(step_parameters["total_expert_insights"])
                if step_parameters["total_expert_insights"]
                and isinstance(step_parameters["total_expert_insights"], list)
                else 0,
                analysis_insights_count=len(step_parameters["analysis_expert_insights"])
                if step_parameters["analysis_expert_insights"]
                and isinstance(step_parameters["analysis_expert_insights"], list)
                else 0,
                yaml_insights_count=len(step_parameters["yaml_expert_insights"])
                if step_parameters["yaml_expert_insights"]
                and isinstance(step_parameters["yaml_expert_insights"], list)
                else 0,
            )

            runtime = InProcessRuntime()
            runtime.start()

            try:
                # Track orchestration start using BaseStepState timing infrastructure
                self.state.set_orchestration_start()

                await self.telemetry.update_agent_activity(
                    process_id=process_id,
                    agent_name="Conversation_Manager",
                    action="expert_collaboration_starting",
                    message_preview="Starting expert documentation discussion with specialist agents",
                )

                orchestration_result = await self._orchestrator.invoke(
                    task=rendered_task, runtime=runtime
                )

                # Wait for the results
                _ = await orchestration_result.get()

                # Capture orchestration end timing using BaseStepState infrastructure
                self.state.set_orchestration_end()
                orchestration_duration = self.state.orchestration_duration or 0.0

                # Track successful orchestration
                await self.telemetry.update_agent_activity(
                    process_id=process_id,
                    agent_name="Conversation_Manager",
                    action="expert_collaboration_completed",
                    message_preview=f"Expert documentation discussion completed successfully in {orchestration_duration:.1f}s",
                )

                ###############################################################
                # Make a reference to the Document result
                ###############################################################
                # Add null safety checks for critical objects
                if not self._orchestrator or not self._orchestrator._manager:
                    logger.error(
                        "[FAILED] Orchestrator or manager is None - cannot retrieve documentation results"
                    )
                    raise RuntimeError(
                        "Orchestrator or manager not properly initialized"
                    )

                document_output = self._orchestrator._manager.final_termination_result

                if document_output is None:
                    logger.error(
                        "[FAILED] Documentation output is None - orchestration may have failed"
                    )
                    raise RuntimeError(
                        "Documentation orchestration failed to produce results"
                    )

                # Set Step State
                # self.step_state = DocumentationStepState(
                #     name="DocumentationStepState",
                #     version="1.0",
                #     final_result=document_output,
                #     reports=document_output.termination_output.aggregated_results,
                #     documentation_completed=True,
                # )
                if document_output.is_hard_terminated:
                    # SCENARIO 1: Hard termination -> PERMANENT FAILURE (using new pattern)
                    logger.info(
                        "[PERMANENT_FAILURE] Hard termination detected - processing as permanent failure"
                    )
                    await self._process_hard_termination_as_failure(document_output, process_id)
                else:
                    # Success case: soft termination = successful completion
                    # CRITICAL: Validate complete data population for success cases
                    if document_output.termination_output is None:
                        error_msg = "CRITICAL ERROR: Documentation step completed successfully but termination_output is None. This indicates incomplete agent response and will cause pipeline failures."
                        logger.error(f"[VALIDATION_ERROR] {error_msg}")
                        raise RuntimeError(error_msg)

                    # Additional validation for successful completion
                    termination_output = document_output.termination_output
                    validation_errors = []

                    # Validate aggregated_results is populated
                    if not termination_output.aggregated_results:
                        validation_errors.append("aggregated_results is None")
                    else:
                        # Validate key fields in aggregated results
                        agg_results = termination_output.aggregated_results
                        if (
                            not agg_results.executive_summary
                            or agg_results.executive_summary.strip() == ""
                        ):
                            validation_errors.append("executive_summary is empty")
                        if (
                            not agg_results.total_files_processed
                            or agg_results.total_files_processed == 0
                        ):
                            validation_errors.append(
                                "total_files_processed is 0 or None"
                            )
                        if (
                            not agg_results.overall_success_rate
                            or agg_results.overall_success_rate.strip() == ""
                        ):
                            validation_errors.append("overall_success_rate is empty")

                    # Validate generated_files is populated
                    if not termination_output.generated_files:
                        validation_errors.append("generated_files is None")
                    else:
                        gen_files = termination_output.generated_files
                        if not gen_files.documentation:
                            validation_errors.append(
                                "generated_files.documentation is empty or None"
                            )
                        if (
                            not gen_files.total_files_generated
                            or gen_files.total_files_generated == 0
                        ):
                            validation_errors.append(
                                "generated_files.total_files_generated is 0 or None"
                            )

                    # Validate expert collaboration data
                    if not termination_output.expert_collaboration:
                        validation_errors.append("expert_collaboration is None")
                    else:
                        expert_collab = termination_output.expert_collaboration
                        if not expert_collab.participating_experts:
                            validation_errors.append("participating_experts is empty")
                        if not expert_collab.expert_insights:
                            validation_errors.append("expert_insights is empty")

                    if validation_errors:
                        error_msg = f"Documentation step validation failed - incomplete agent response: {'; '.join(validation_errors)}"
                        logger.error(f"[VALIDATION_ERROR] {error_msg}")
                        raise RuntimeError(error_msg)

                    logger.info(
                        f"[SUCCESS] Documentation generation completed successfully with complete data: {document_output.reason}"
                    )

                    # Create structured result
                    result = {
                        "process_id": process_id,
                        "workspace_file_folder": workspace_file_folder,
                        "output_file_folder": output_file_folder,
                        "container_name": container_name,
                        "result_file_name": "migration_report.md",
                        "state": document_output,
                        "execution_time": orchestration_duration,
                    }

                    # Invoke Event Sink - Task Recording
                    await context.emit_event(
                        process_event="OnStateChange",
                        data=result,
                    )

                    safe_log(
                        logger,
                        "info",
                        "[SUCCESS] Group chat documentation completed for process {process_id}",
                        process_id=process_id,
                    )

                    # Track step completion
                    await self.telemetry.update_agent_activity(
                        process_id=process_id,
                        agent_name="Conversation_Manager",
                        action="expert_step_completed",
                        message_preview=f"Expert documentation discussion completed for process {process_id}",
                    )

                    ######################################################
                    # Set up state values
                    #####################################################
                    # Base fields required by KernelProcessStepState
                    # name: str = Field(
                    #     default="DocumentationStepState", description="Name of the step state"
                    # )
                    # version: str = Field(default="1.0", description="Version of the step state")
                    # result: bool = False
                    # documentation_generated: str = ""
                    # reports: AggregatedResults | None = None
                    # documentation_completed: bool = False
                    # final_result: Documentation_ExtendedBooleanResult | None = None
                    # reason: str = Field(default="", description="Reason for failure if any")
                    self._ensure_state_initialized()
                    assert self.state is not None  # For type checker
                    self.state.name = "DocumentationStep"
                    self.state.result = True
                    self.state.version = "1.0"
                    self.state.final_result = document_output
                    self.state.reason = document_output.reason
                    # Extract validated termination_output
                    self.state.reports = termination_output.aggregated_results
                    generated_files = termination_output.generated_files

                    if (
                        generated_files is not None
                        and hasattr(generated_files, "documentation")
                        and generated_files.documentation is not None
                    ):
                        self.state.documentation_generated = (
                            # Get primary migration report from generated files
                            next(
                                (
                                    f.file_name
                                    for f in generated_files.documentation
                                    if f.file_type == "migration_report"
                                ),
                                "migration_report.md",  # fallback
                            )
                        )
                    else:
                        self.state.documentation_generated = (
                            "migration_report.md"  # fallback
                        )
                        # Success case but no termination_output - use sensible defaults
                        logger.info(
                            "[INFO] Using default values for successful documentation completion"
                        )
                        self.state.reports = None
                        self.state.documentation_generated = "migration_report.md"

                    self.state.documentation_completed = True

            finally:
                # Always clean up runtime
                await runtime.stop_when_idle()
                logger.info("[CLEANUP] Documentation runtime cleaned up")
        except Exception as e:
            error_message = str(e)

            # Ensure state is initialized before using
            self._ensure_state_initialized()
            assert self.state is not None  # For type checker

            # Capture execution end time for comprehensive failure context
            self.state.set_execution_end()

            # Calculate time to failure (setup + error handling time)
            time_to_failure = self.state.total_execution_duration or 0.0

            # Collect system failure context with full stack trace following established pattern
            failure_collector = StepFailureCollector()
            system_context = await failure_collector.collect_system_failure_context(
                error=e,
                step_name="DocumentationStep",
                process_id=process_id,
                context_data=context_data,
                step_start_time=self.state.execution_start_time,
                step_phase="expert_documentation_generation",
            )

            # Simplified error handling - treat all errors as critical
            logger.error(f"[CRITICAL] Documentation step critical error: {error_message}")

            # Track critical error in telemetry
            await self.telemetry.update_agent_activity(
                process_id=process_id,
                agent_name="Conversation_Manager",
                action="expert_step_critical_error",
                message_preview=f"Critical error in expert documentation: {error_message[:100]}",
            )

            # Set state for migration service to read - PRIMARY failure indicator
            self.state.result = False
            self.state.reason = f"Critical error: {error_message}"
            self.state.failure_context = (
                await failure_collector.create_step_failure_state(
                    reason=f"Documentation failed: {error_message}",
                    execution_time=time_to_failure,
                    files_attempted=[],  # Documentation doesn't process individual files
                    system_failure_context=system_context,
                )
            )

            logger.error(
                f"[CRITICAL] Documentation step failed with comprehensive failure context - time to failure: {time_to_failure:.2f}s"
            )

            # Enhanced error logging
            safe_log(
                logger,
                "error",
                "[FAILED] Documentation failed with critical error: {error}",
                error=e,
            )
        finally:
            logger.info("[SUCCESS] Documentation step execution completed")
