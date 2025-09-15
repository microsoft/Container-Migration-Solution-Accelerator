"""
Migration Service Module - Enterprise Queue-Based Processing Engine

Implements Microsoft Content Processing Solution Accelerator patterns for scalable
Kubernetes migration processing with Azure OpenAI o3 integration.

Features:
- Queue-based processing with timeout protection
- Multi-agent orchestration via Semantic Kernel
- DefaultAzureCredential authentication ✅
- Comprehensive error classification and retry logic
"""

from dataclasses import dataclass
from enum import Enum
import logging
import time
from typing import Any

from semantic_kernel.processes.kernel_process import KernelProcess
from semantic_kernel.processes.kernel_process.kernel_process_event import (
    KernelProcessEvent,
)
from semantic_kernel.processes.local_runtime.local_kernel_process import start

from libs.base.KernelAgent import semantic_kernel_agent
from libs.processes.aks_migration_process import AKSMigrationProcess
from libs.reporting import (
    FailureSeverity,
    FailureType,
    MigrationReportCollector,
    MigrationReportGenerator,
)

# Show clean completion message and clear agent comments
from libs.steps.documentation_step import DocumentationStepState
from utils.agent_telemetry import TelemetryManager
from utils.error_classifier import ErrorClassification, classify_error

logger = logging.getLogger(__name__)


def format_step_status(step_name: str, result: bool | None, reason: str = "") -> str:
    """
    Format step status with user-friendly messages.

    Args:
        step_name: Name of the migration step
        result: Step result (None=not started, True=success, False=failed)
        reason: Additional context for failed steps

    Returns:
        User-friendly status message
    """
    if result is None:
        return f"{step_name}: ⏳ Not started yet"
    elif result is True:
        return f"{step_name}: ✅ Completed successfully"
    else:  # result is False
        reason_text = reason or "Encountered issues"
        return f"{step_name}: ❌ {reason_text}"


class ProcessStatus(Enum):
    """Migration process execution status"""

    INITIALIZING = "initializing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class MigrationEngineResult:
    """
    Result of migration engine execution following Content Processing Accelerator patterns

    Provides comprehensive execution metadata for queue processors and monitoring systems
    """

    success: bool
    process_id: str
    execution_time: float
    status: ProcessStatus
    error_message: str | None = None
    error_classification: ErrorClassification | None = None
    final_state: Any | None = None
    timestamp: float | None = None
    requires_immediate_retry: bool = (
        False  # NEW: State-based immediate retry flag for hard termination
    )

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

    @property
    def is_retryable(self) -> bool:
        """Determine if this result indicates a retryable failure"""
        if self.success:
            return False

        # Check error classification for retryable types
        return self.error_classification == ErrorClassification.RETRYABLE


class MigrationProcessor:
    """
    Enterprise Migration Processing Engine

    Implements Microsoft Content Processing Solution Accelerator patterns:
    - Stateless processing for queue-based workloads
    - Comprehensive error handling and classification
    - Resource lifecycle management
    - Enterprise telemetry integration
    - Timeout and circuit breaker protection

    Designed for competing consumers pattern with Azure Service Bus or Queue Storage
    """

    def __init__(
        self,
        app_context: Any | None = None,
        debug_mode: bool = False,
        timeout_minutes: int = 25,
    ):
        self.app_context = app_context
        self.debug_mode = debug_mode
        self.timeout_minutes = timeout_minutes
        self.kernel_agent: semantic_kernel_agent | None = None
        self.migration_process: KernelProcess | None = None

        # Initialize telemetry instance for this processor
        self.telemetry = TelemetryManager(app_context)

        # Report collector for comprehensive failure reporting
        self._report_collector: MigrationReportCollector | None = None

    async def initialize(self, **kwargs):
        """Initialize the migration engine components with proper error handling"""
        try:
            # Create kernel agent with configuration
            logger.info(
                f"[DEBUG] About to create semantic_kernel_agent with debug_mode={self.debug_mode}"
            )
            self.kernel_agent = semantic_kernel_agent(
                app_context=self.app_context,
                debug_mode=self.debug_mode,
                **kwargs,
            )
            logger.info("[DEBUG] semantic_kernel_agent created successfully")

            # Initialize kernel agent async components
            logger.info("[DEBUG] About to initialize kernel agent async components")
            await self.kernel_agent.initialize_async()
            logger.info("[DEBUG] Kernel agent async initialization completed")

            if self.debug_mode:
                logger.info("Kernel agent initialized successfully")

            if not self.kernel_agent:
                raise RuntimeError("Failed to create kernel agent")

            # Create the migration process instance with telemetry
            self.migration_process = AKSMigrationProcess.create_process()
            if not self.migration_process:
                raise RuntimeError("Failed to create migration process")

            if self.debug_mode:
                logger.info("Migration processor initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize migration processor: {e}")
            raise

    async def execute_migration(
        self, process_id: str, user_id: str, migration_request: dict[str, Any]
    ) -> MigrationEngineResult:
        """
        Execute migration process following enterprise queue processing patterns

        Args:
            process_id: Unique process identifier for tracking and telemetry
            migration_request: Migration parameters and configuration

        Returns:
            MigrationEngineResult with comprehensive execution metadata
        """
        if not process_id:
            raise ValueError("Process ID is required for tracking and telemetry")

        if not user_id:
            raise ValueError("User ID is required for tracking and telemetry")

        process_start_time = time.time()

        # Initialize comprehensive report collector
        self._report_collector = MigrationReportCollector(process_id)

        try:
            # Initialize process telemetry tracking - single initialization
            await self.telemetry.init_process(
                process_id, "Initialization", "MigrationProcessor"
            )

            await self.telemetry.update_agent_activity(
                process_id,
                "Conversation_Manager",
                "service_starting",
                "Starting Queue Migration Service",
            )

            # Phase transitions will be handled by each step when they start executing
            await self.telemetry.update_agent_activity(
                process_id,
                "Conversation_Manager",
                "process_starting",
                "Initializing AKS migration process",
            )

            if self.debug_mode:
                logger.info(f"Starting migration process: {process_id}")

            # Create initial event from migration request
            # add app_context to migration_request
            migration_request["app_context"] = self.app_context

            initial_event = KernelProcessEvent(
                id="StartMigration", data=migration_request
            )

            # Execute with timeout protection
            final_state = await self._execute_with_timeout(
                initial_event, process_id, user_id
            )
            execution_time = time.time() - process_start_time

            # Evaluate process completion status
            process_evaluation = self._evaluate_process_success(final_state)

            if process_evaluation == "RUNNING":
                # Process is still running - return running status without deleting message
                logger.info(
                    "Process still in progress - keeping message in queue for monitoring"
                )
                return MigrationEngineResult(
                    success=False,  # Not success yet, but not failed either
                    process_id=process_id,
                    execution_time=execution_time,
                    status=ProcessStatus.RUNNING,
                    error_message="Process still in progress",
                    error_classification=ErrorClassification.NON_RETRYABLE,  # Don't retry running process
                    final_state=final_state,
                )
            elif process_evaluation is True:
                ########################################################################################################
                # ENHANCED: Extract and share final_result with telemetry system
                # Collect results from each completed step and share with telemetry
                ########################################################################################################

                # Get the final results from each step
                step_results_for_telemetry = {}
                final_outcome_data = {}

                if (
                    final_state
                    and hasattr(final_state, "steps")
                    and len(final_state.steps) >= 4
                ):
                    try:
                        # Extract results from each step for telemetry
                        step_names = ["Analysis", "Design", "YAML", "Documentation"]

                        for i, step_name in enumerate(step_names):
                            if i < len(final_state.steps):
                                step_state = final_state.steps[i].state.state
                                if (
                                    step_state
                                    and hasattr(step_state, "final_result")
                                    and step_state.final_result
                                ):
                                    step_results_for_telemetry[step_name] = {
                                        "result": getattr(
                                            step_state.final_result, "result", True
                                        ),
                                        "reason": getattr(
                                            step_state.final_result, "reason", ""
                                        ),
                                        "termination_output": getattr(
                                            step_state.final_result,
                                            "termination_output",
                                            {},
                                        ),
                                    }

                        # Get comprehensive final result from Documentation step (contains all phase results)
                        if len(final_state.steps) > 3:  # Documentation step is index 3
                            document_result: DocumentationStepState = final_state.steps[
                                3
                            ].state.state  # type: ignore
                            if hasattr(document_result, "final_result") and hasattr(
                                document_result.final_result, "termination_output"
                            ):
                                final_result = (
                                    document_result.final_result.termination_output
                                )  # type: ignore
                                final_outcome_data = (
                                    final_result
                                    if isinstance(final_result, dict)
                                    else {}
                                )

                                logger.info(
                                    f"[SUCCESS] Extracted final results - Keys: {list(final_outcome_data.keys()) if final_outcome_data else 'None'}"
                                )

                        # === ENHANCED: Extract comprehensive UI data for telemetry ===
                        ui_telemetry_data = await self._extract_ui_telemetry_data(
                            final_state,
                            step_results_for_telemetry,
                            final_outcome_data,
                            process_id,
                        )

                        # Record each step result in telemetry
                        for (
                            step_name,
                            result_data,
                        ) in step_results_for_telemetry.items():
                            await self.telemetry.record_step_result(
                                process_id=process_id,
                                step_name=step_name,
                                step_result=result_data,
                            )

                        # Record the comprehensive final outcome with UI data
                        if final_outcome_data:
                            await self.telemetry.record_final_outcome(
                                process_id=process_id,
                                outcome_data=final_outcome_data,
                                success=True,
                            )
                            logger.info("[SUCCESS] Final outcome recorded in telemetry")
                        else:
                            logger.warning("[SUCCESS] No final outcome data to record")

                        # === NEW: Record UI-optimized telemetry data ===
                        if ui_telemetry_data:
                            await self.telemetry.record_ui_data(
                                process_id=process_id,
                                ui_data=ui_telemetry_data,
                            )
                            logger.info(
                                f"[UI-TELEMETRY] Recorded comprehensive UI data - "
                                f"Files: {len(ui_telemetry_data.get('file_manifest', {}).get('converted_files', []))}, "
                                f"Failed: {len(ui_telemetry_data.get('file_manifest', {}).get('failed_files', []))}, "
                                f"Reports: {len(ui_telemetry_data.get('file_manifest', {}).get('report_files', []))}"
                            )

                    except Exception as telemetry_error:
                        logger.error(
                            f"[ERROR] Failed to record results in telemetry: {telemetry_error}"
                        )
                        # Continue with success despite telemetry error

                # Generate success report
                await self._generate_success_report(process_id, execution_time)
                # update completed
                await self._handle_success(process_id, execution_time)

                return MigrationEngineResult(
                    success=True,
                    process_id=process_id,
                    execution_time=execution_time,
                    status=ProcessStatus.COMPLETED,
                    final_state=final_state,
                )
            else:
                # Process has completed but with failures - collect detailed error information
                # NOTE: This block should only run for actually FAILED processes, not RUNNING ones
                hard_termination_reason = None
                failed_steps = []
                requires_immediate_retry = (
                    False  # NEW: State-based immediate retry detection
                )
                termination_details_for_telemetry = {}  # NEW: Telemetry data collection

                # Collect comprehensive error information from all steps
                required_steps = 4  # analysis(0), design(1), yaml(2), documentation(3)
                # failed_steps = [
                #     i
                #     for i in range(required_steps)
                #     if not final_state.steps[i].state.state.result
                # ]
                for _step_index in range(required_steps):
                    if _step_index >= len(final_state.steps):
                        break  # Stop if we don't have enough steps
                    step = final_state.steps[_step_index]
                    step_state = step.state.state
                    step_name = (
                        f"Step_{_step_index}"
                        if not step_state
                        else getattr(step_state, "name", f"Step_{_step_index}")
                    )

                    # NEW: Check for state-based immediate retry flag
                    if (
                        step_state is not None
                        and hasattr(step_state, "requires_immediate_retry")
                        and step_state.requires_immediate_retry
                    ):
                        requires_immediate_retry = True

                        # Collect termination details for telemetry
                        if (
                            hasattr(step_state, "termination_details")
                            and step_state.termination_details
                        ):
                            termination_details_for_telemetry[step_name] = (
                                step_state.termination_details
                            )
                            logger.info(
                                f"[IMMEDIATE_RETRY] Step {step_name} requires immediate retry - "
                                f"termination details collected for telemetry"
                            )

                    if step_state is not None and hasattr(step_state, "final_result"):
                        final_result = step_state.final_result

                        # Check for hard termination
                        if (
                            hasattr(final_result, "is_hard_terminated")
                            and final_result.is_hard_terminated
                        ):
                            hard_termination_reason = final_result.reason
                            failed_steps.append(
                                f"{step_name}: HARD_TERMINATED - {final_result.reason}"
                            )

                        # Check for step failure (result = False)
                        elif (
                            hasattr(step_state, "result") and step_state.result is False
                        ):
                            # NEW: Check for rich failure context first
                            if (
                                hasattr(step_state, "failure_context")
                                and step_state.failure_context
                            ):
                                failure_context = step_state.failure_context

                                # Extract detailed error information from SystemFailureContext
                                if failure_context.system_failure_context:
                                    sys_context = failure_context.system_failure_context

                                    # Build comprehensive error message with full stack trace
                                    detailed_reason = (
                                        f"{failure_context.reason}\n"
                                        f"Error: {sys_context.error_type}: {sys_context.error_message}\n"
                                        f"Full Stack Trace:\n{sys_context.stack_trace}\n"
                                        f"(Execution time: {failure_context.execution_time:.2f}s)"
                                    )
                                else:
                                    detailed_reason = failure_context.reason

                                failed_steps.append(
                                    format_step_status(
                                        step_name, False, detailed_reason
                                    )
                                )
                            else:
                                # Fallback to basic reason for backward compatibility
                                failure_reason = getattr(
                                    step_state, "reason", "Unknown failure"
                                )
                                failed_steps.append(
                                    format_step_status(step_name, False, failure_reason)
                                )

                        # Check for exceptions or errors in final_result
                        elif hasattr(final_result, "error_message"):
                            failed_steps.append(
                                f"{step_name}: ERROR - {final_result.error_message}"
                            )

                    # Also check step state directly for failures
                    elif (
                        step_state is not None
                        and hasattr(step_state, "result")
                        and step_state.result is False
                    ):
                        # NEW: Check for rich failure context first
                        if (
                            hasattr(step_state, "failure_context")
                            and step_state.failure_context
                        ):
                            failure_context = step_state.failure_context

                            # Extract detailed error information from SystemFailureContext
                            if failure_context.system_failure_context:
                                sys_context = failure_context.system_failure_context

                                # Build comprehensive error message with full stack trace
                                detailed_reason = (
                                    f"{failure_context.reason}\n"
                                    f"Error: {sys_context.error_type}: {sys_context.error_message}\n"
                                    f"Full Stack Trace:\n{sys_context.stack_trace}\n"
                                    f"(Execution time: {failure_context.execution_time:.2f}s)"
                                )
                            else:
                                detailed_reason = failure_context.reason

                            failed_steps.append(
                                format_step_status(step_name, False, detailed_reason)
                            )
                        else:
                            # Fallback to basic reason for backward compatibility
                            failure_reason = getattr(
                                step_state,
                                "reason",
                                "Step failed without specific reason",
                            )
                            failed_steps.append(
                                format_step_status(step_name, False, failure_reason)
                            )

                # Build comprehensive error message
                if hard_termination_reason:
                    reason_message = (
                        f"Migration process hard terminated: {hard_termination_reason}"
                    )
                elif failed_steps:
                    reason_message = f"Migration process failed in {len(failed_steps)} step(s): {'; '.join(failed_steps)}"
                else:
                    reason_message = f"Migration process completed with failures (no specific error details available from {len(final_state.steps)} steps)"

                await self._handle_failure(
                    process_id,
                    reason_message,
                    execution_time,
                    ErrorClassification.NON_RETRYABLE,
                    is_final_failure=True,  # This is final failure
                )

                # NEW: Enhanced telemetry for immediate retry scenarios
                failure_details = {
                    "hard_termination_reason": hard_termination_reason,
                    "failed_steps": failed_steps,
                    "total_steps": len(final_state.steps),
                    "execution_time": execution_time,
                    "requires_immediate_retry": requires_immediate_retry,  # NEW
                    "termination_details": termination_details_for_telemetry,  # NEW
                }

                # Record failure outcome in telemetry with enhanced retry information
                try:
                    await self.telemetry.record_failure_outcome(
                        process_id=process_id,
                        error_message=reason_message,
                        failed_step="migration_process",
                        failure_details=failure_details,
                    )

                    # NEW: Additional telemetry for immediate retry scenarios
                    if requires_immediate_retry:
                        logger.info(
                            f"[TELEMETRY] Immediate retry scenario detected for process {process_id} - "
                            f"termination details: {len(termination_details_for_telemetry)} steps"
                        )

                except Exception as telemetry_error:
                    logger.error(
                        f"Failed to record failure outcome in telemetry: {telemetry_error}"
                    )

                return MigrationEngineResult(
                    success=False,
                    process_id=process_id,
                    execution_time=execution_time,
                    status=ProcessStatus.FAILED,
                    error_message=reason_message,
                    error_classification=ErrorClassification.RETRYABLE,
                    requires_immediate_retry=requires_immediate_retry,  # NEW: State-based immediate retry flag
                    final_state=final_state,
                )

        except TimeoutError:
            execution_time = time.time() - process_start_time
            timeout_exception = TimeoutError(
                f"Migration process timed out after {self.timeout_minutes} minutes"
            )

            # Create comprehensive error message
            full_error_message = self._create_comprehensive_error_message(
                timeout_exception
            )
            logger.error(f"[TIMEOUT] {full_error_message}")

            # Record timeout failure in report collector
            if self._report_collector:
                _failure_content = self._report_collector.record_failure(
                    timeout_exception,
                    failure_type=FailureType.TIMEOUT,
                    severity=FailureSeverity.HIGH,
                )

            await self._handle_failure(
                process_id,
                full_error_message,
                execution_time,
                ErrorClassification.NON_RETRYABLE,  # Not RETRYABLE At this moment
                is_final_failure=True,  # This is final failure
            )

            # Generate comprehensive failure report
            await self._generate_failure_report(
                process_id, execution_time, ProcessStatus.TIMEOUT
            )

            return MigrationEngineResult(
                success=False,
                process_id=process_id,
                execution_time=execution_time,
                status=ProcessStatus.TIMEOUT,
                error_message=full_error_message,
                error_classification=ErrorClassification.RETRYABLE,
                requires_immediate_retry=False,  # Timeouts use normal exponential backoff
            )

        except Exception as e:
            import traceback

            execution_time = time.time() - process_start_time

            # Capture full traceback immediately while exception context is active
            full_traceback = traceback.format_exc()

            # Record exception failure in report collector
            if self._report_collector:
                self._report_collector.record_failure(e)

            # Classify error for retry decision
            error_classification = classify_error(e)

            # Create comprehensive error message with full details
            full_error_message = self._create_comprehensive_error_message(e)
            logger.error(f"[FAILED] {full_error_message}")

            await self._handle_failure(
                process_id,
                full_error_message,  # Pass full error message instead of str(e)
                execution_time,
                error_classification,
                full_traceback,
                is_final_failure=True,
                # is_final_failure=(
                #     error_classification != ErrorClassification.RETRYABLE
                # ),
            )  # Generate comprehensive failure report
            await self._generate_failure_report(
                process_id, execution_time, ProcessStatus.FAILED
            )

            return MigrationEngineResult(
                success=False,
                process_id=process_id,
                execution_time=execution_time,
                status=ProcessStatus.FAILED,
                error_message=full_error_message,  # Use the full error message here too
                error_classification=error_classification,
                requires_immediate_retry=False,  # General exceptions use normal exponential backoff
            )

    async def _execute_with_timeout(
        self, initial_event: KernelProcessEvent, process_id: str, user_id: str
    ):
        """Execute migration process with timeout protection"""
        if not self.migration_process or not self.kernel_agent:
            raise RuntimeError("Migration processor not properly initialized")

        # Execute process without timeout protection (timeout was causing hangs)
        # Process execution telemetry is now handled by individual steps with Conversation_Manager

        async with await start(
            process=self.migration_process,
            kernel=self.kernel_agent.kernel,
            initial_event=initial_event,
        ) as process_context:
            if self.debug_mode:
                logger.info(f"[PROCESS] Migration process started: {process_id}")
                logger.info(f"Initial event: {initial_event.id}")

            # Get final state when process completes
            final_state = await process_context.get_state()
            return final_state

    def _evaluate_process_success(self, final_state) -> bool | str:
        """Evaluate if the migration process completed successfully

        Returns:
            True: Process completed successfully
            False: Process failed
            "RUNNING": Process is still in progress
        """
        try:
            # Check if ALL 4 steps (analysis, design, yaml, documentation) have completed successfully
            # Process is only complete when all steps exist and all have result=True
            required_steps = 4  # analysis(0), design(1), yaml(2), documentation(3)

            current_steps = len(final_state.steps)

            # If we have fewer than 4 steps, the process is still in progress (not failed)
            if current_steps < required_steps:
                logger.info(
                    f"Process in progress - {current_steps} of {required_steps} steps completed"
                )
                # Only mark as failed if we have 0 steps (process never started)
                if current_steps == 0:
                    logger.info("No steps executed - process failed to start")
                    return False
                else:
                    logger.info("Process still running - not evaluating success yet")
                    return "RUNNING"  # Return special status for running process

            # All 4 steps must exist and have result=True
            all_steps_successful = all(
                final_state.steps[i].state.state.result for i in range(required_steps)
            )

            if all_steps_successful:
                logger.info("All 4 migration steps completed successfully")
            else:
                failed_steps = [
                    i
                    for i in range(required_steps)
                    if not final_state.steps[i].state.state.result
                ]
                logger.info(f"Steps {failed_steps} have not completed successfully")

            return all_steps_successful

        except Exception as e:
            logger.error(f"Error evaluating process success: {e}")
            return False

    async def _handle_success(self, process_id: str, execution_time: float):
        """Handle successful migration completion"""
        if self.debug_mode:
            logger.info(f"[SUCCESS] Migration process completed: {process_id}")
            logger.info(f"Total execution time: {execution_time:.2f} seconds")

        # Update process status to completed using both class and global methods
        await self.telemetry.update_process_status(
            process_id=process_id, status="completed"
        )

        # Update final process status
        await self.telemetry.update_agent_activity(
            process_id=process_id,
            agent_name="Conversation_Manager",
            action="migration_process_completed",
            message_preview="Migration conversation completed successfully",
        )

        # Mark all participant agents as completed
        await self.telemetry.complete_all_participant_agents(process_id=process_id)

        # Show clean completion message - use telemetry instance
        process = await self.telemetry.get_current_process(process_id=process_id)
        if process:
            logger.info("=" * 60)
            logger.info("🎉 MIGRATION COMPLETED SUCCESSFULLY!")
            logger.info(f"✅ Process {process.id} finished")
            logger.info(f"📊 Phase: {process.phase}")
            logger.info("=" * 60)

    async def _handle_failure(
        self,
        process_id: str,
        error_message: str,
        execution_time: float,
        error_classification: ErrorClassification,
        full_traceback: str | None = None,
        is_final_failure: bool = True,
    ):
        """Handle migration process failure with comprehensive logging"""

        logger.error(
            f"[FAILURE] Process {process_id} failed after {execution_time:.2f}s"
        )
        logger.error(f"[ERROR] {error_message}")
        logger.error(f"[CLASSIFICATION] {error_classification.value}")

        # Use provided traceback or generate if not provided
        if full_traceback is None:
            import traceback

            full_traceback = traceback.format_exc()

        if self.debug_mode:
            logger.error(f"[TRACEBACK] {full_traceback}")

        try:
            # Only update process status to failed if this is a final failure (not retryable)
            if is_final_failure:
                await self.telemetry.update_process_status(
                    process_id=process_id, status="failed"
                )
            else:  # is_final_failure should be true as always at this moment.
                # For retryable failures, keep status as "running" since retry will happen
                await self.telemetry.update_process_status(
                    process_id=process_id, status="running"
                )

            # Update Conversation_Manager agent activity to show failure or retry
            if is_final_failure:
                await self.telemetry.update_agent_activity(
                    process_id=process_id,
                    agent_name="Conversation_Manager",
                    action="migration_process_failed",
                    message_preview=f"Migration conversation failed: {error_message}",
                )
            else:
                await self.telemetry.update_agent_activity(
                    process_id=process_id,
                    agent_name="Conversation_Manager",
                    action="migration_process_retrying",
                    message_preview=f"Migration conversation will retry: {error_message}",
                )

            # Only record process failure and mark agents as failed for final failures
            if is_final_failure:
                # Record detailed failure information
                await self.telemetry.record_failure(
                    process_id=process_id,
                    failure_reason=error_message,
                    failure_details=f"Process failed after {execution_time:.2f}s - Step: migration_process",
                    stack_trace=full_traceback,
                )

                # Mark all participant agents as failed by recording the failure
                await self.telemetry.record_failure(
                    process_id=process_id,
                    failure_reason=error_message,
                    failure_step="migration_process",
                )
            else:
                # For retryable failures, just log the retry attempt
                logger.info(
                    f"[RETRY] Process {process_id} will be retried due to: {error_message}"
                )

        except Exception as update_error:
            import traceback

            logger.error(f"Failed to record process failure details: {update_error}")
            logger.error(f"Update error type: {type(update_error).__name__}")
            logger.error(f"Update error traceback: {traceback.format_exc()}")

    def _create_comprehensive_error_message(self, exception: Exception) -> str:
        """
        Create a comprehensive error message that includes full exception details without truncation

        Args:
            exception: The exception to create a comprehensive message for

        Returns:
            A detailed error message with exception type, message, and context
        """
        try:
            exception_type = type(exception).__name__
            exception_message = str(exception)

            # Get the exception arguments if available for more context
            exception_args = getattr(exception, "args", ())

            # Create comprehensive message
            if exception_args and len(exception_args) > 1:
                # Multiple args - include all for full context
                full_message = (
                    f"Migration process failed - {exception_type}: {exception_message}"
                )
                full_message += f" | Additional context: {', '.join(str(arg) for arg in exception_args[1:])}"
            elif hasattr(exception, "__cause__") and exception.__cause__:
                # Include cause if available
                cause = exception.__cause__
                full_message = (
                    f"Migration process failed - {exception_type}: {exception_message}"
                )
                full_message += f" | Caused by: {type(cause).__name__}: {str(cause)}"
            elif hasattr(exception, "__context__") and exception.__context__:
                # Include context if available
                context = exception.__context__
                full_message = (
                    f"Migration process failed - {exception_type}: {exception_message}"
                )
                full_message += f" | Context: {type(context).__name__}: {str(context)}"
            else:
                # Simple case - just type and message
                full_message = (
                    f"Migration process failed - {exception_type}: {exception_message}"
                )

            # Add module/class information if available
            if hasattr(exception, "__module__"):
                full_message += f" | Module: {exception.__module__}"

            return full_message

        except Exception as e:
            # Fallback to simple string representation if comprehensive formatting fails
            return f"Migration process failed - {type(exception).__name__}: {str(exception)} (Error formatting details: {e})"

    async def cleanup(self):
        """Cleanup resources after processing"""
        try:
            if self.kernel_agent:
                # Perform any necessary cleanup on kernel agent
                # Add specific cleanup logic as needed
                pass

            if self.debug_mode:
                logger.info("[CLEANUP] Migration processor resources cleaned up")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def _generate_success_report(
        self, process_id: str, execution_time: float
    ) -> None:
        """Generate and save success report."""
        if not self._report_collector:
            logger.warning(
                "Report collector not initialized, skipping success report generation"
            )
            return

        try:
            from libs.reporting.models.migration_report import ReportStatus

            # Generate comprehensive success report
            generator = MigrationReportGenerator(self._report_collector)
            report = await generator.generate_failure_report(
                overall_status=ReportStatus.SUCCESS
            )

            # Save reports to telemetry system
            await self._save_report_to_telemetry(report, process_id, "success")

            logger.info(
                f"Generated comprehensive success report for process {process_id}"
            )

        except Exception as e:
            logger.error(f"Failed to generate success report: {e}")

    async def _generate_failure_report(
        self, process_id: str, execution_time: float, status: ProcessStatus
    ) -> None:
        """Generate and save comprehensive failure report."""
        if not self._report_collector:
            logger.warning(
                "Report collector not initialized, skipping failure report generation"
            )
            return

        try:
            from libs.reporting.models.migration_report import ReportStatus

            # Map ProcessStatus to ReportStatus
            report_status_map = {
                ProcessStatus.FAILED: ReportStatus.FAILED,
                ProcessStatus.TIMEOUT: ReportStatus.TIMEOUT,
                ProcessStatus.COMPLETED: ReportStatus.SUCCESS,
            }
            report_status = report_status_map.get(status, ReportStatus.FAILED)

            # Generate comprehensive failure report
            generator = MigrationReportGenerator(self._report_collector)
            report = await generator.generate_failure_report(
                overall_status=report_status
            )

            # Save reports to telemetry system
            await self._save_report_to_telemetry(report, process_id, "failure")

            # Log executive summary for immediate visibility
            logger.error(
                f"Generated comprehensive failure report for process {process_id}"
            )
            logger.error(
                f"Completion: {report.executive_summary.completion_percentage:.1f}%"
            )
            logger.error(
                f"Critical Issues: {report.executive_summary.critical_issues_count}"
            )
            logger.error(f"Files Failed: {report.executive_summary.files_failed}")

            # Log top remediation actions
            if report.remediation_guide and report.remediation_guide.priority_actions:
                logger.info("Top remediation actions:")
                for i, action in enumerate(
                    report.remediation_guide.priority_actions[:3], 1
                ):
                    logger.info(f"{i}. {action.title}: {action.description}")

        except Exception as e:
            logger.error(f"Failed to generate failure report: {e}")

    async def _save_report_to_telemetry(
        self, report, process_id: str, report_type: str
    ) -> None:
        """Save finalized migration report to telemetry system."""
        try:
            from libs.reporting.formatters.json_formatter import JsonReportFormatter
            from libs.reporting.formatters.markdown_formatter import (
                MarkdownReportFormatter,
            )

            # Generate report contents
            markdown_content = MarkdownReportFormatter.format_report(report)
            json_content = JsonReportFormatter.format_report(report)
            exec_summary = MarkdownReportFormatter.format_executive_summary(report)

            # Create comprehensive outcome data for telemetry
            outcome_data = {
                "process_id": process_id,
                "report_type": report_type,
                "report_status": report.overall_status.value
                if hasattr(report, "overall_status")
                else "Unknown",
                "executive_summary": exec_summary,
                "full_report": {
                    "markdown": markdown_content,
                    "json": json_content,
                },
                "report_metadata": {
                    "total_steps": len(report.steps) if hasattr(report, "steps") else 0,
                    "execution_time": getattr(report, "execution_time", 0),
                    "timestamp": getattr(report, "timestamp", None),
                },
                "content_stats": {
                    "markdown_chars": len(markdown_content),
                    "json_chars": len(json_content),
                    "summary_chars": len(exec_summary),
                },
            }

            # Determine success status
            is_success = (
                report_type == "success"
                and hasattr(report, "overall_status")
                and report.overall_status.value == "SUCCESS"
            )

            # Store finalized results in telemetry
            await self.telemetry.record_final_outcome(
                process_id=process_id, outcome_data=outcome_data, success=is_success
            )

            logger.info(
                f"[TELEMETRY] Stored {report_type} report for process {process_id} in telemetry system"
            )
            logger.info(
                f"- Report status: {getattr(report, 'overall_status', 'Unknown')}"
            )
            logger.info(
                f"- Content: {len(markdown_content)} chars markdown, {len(json_content)} chars JSON"
            )

        except Exception as e:
            logger.error(f"Failed to save report to telemetry: {e}")

    async def _extract_ui_telemetry_data(
        self,
        final_state: Any,
        step_results: dict[str, dict],
        final_outcome_data: dict,
        process_id: str,
    ) -> dict:
        """
        Extract comprehensive UI-optimized data for telemetry integration.

        This method creates a rich data structure specifically designed for
        frontend consumption, including file manifests, dashboard metrics,
        and downloadable artifacts.
        """
        try:
            ui_data = {
                "file_manifest": {
                    "source_files": [],
                    "converted_files": [],
                    "failed_files": [],  # NEW: Track failed files with detailed reasons
                    "report_files": [],
                },
                "dashboard_metrics": {
                    "completion_percentage": 0.0,
                    "files_processed": 0,
                    "files_successful": 0,
                    "files_failed": 0,
                    "total_execution_time": "0s",
                    "status_summary": "Processing completed",
                },
                "step_progress": [],
                "downloadable_artifacts": {
                    "converted_configs": [],
                    "reports": [],
                    "documentation": [],
                    "archive": None,
                },
            }

            # === 1. Extract File Manifest ===
            await self._extract_file_manifest(
                ui_data, final_state, final_outcome_data, step_results, process_id
            )

            # === 2. Calculate Dashboard Metrics ===
            await self._calculate_dashboard_metrics(ui_data, step_results)

            # === 3. Build Step Progress ===
            await self._build_step_progress(ui_data, step_results, final_state)

            # === 4. Collect Downloadable Artifacts ===
            await self._collect_downloadable_artifacts(
                ui_data, final_outcome_data, process_id
            )

            logger.info(
                f"[UI-TELEMETRY] Extracted UI data - "
                f"Converted files: {len(ui_data['file_manifest']['converted_files'])}, "
                f"Failed files: {len(ui_data['file_manifest']['failed_files'])}, "
                f"Reports: {len(ui_data['file_manifest']['report_files'])}, "
                f"Completion: {ui_data['dashboard_metrics']['completion_percentage']:.1f}%"
            )

            return ui_data

        except Exception as e:
            logger.error(f"[UI-TELEMETRY] Failed to extract UI data: {e}")
            return {}

    async def _extract_file_manifest(
        self,
        ui_data: dict,
        final_state: Any,
        final_outcome_data: dict,
        step_results: dict[str, dict],
        process_id: str,
    ) -> None:
        """Extract comprehensive file manifest for UI display."""
        try:
            # Get source files from Analysis step
            if (
                final_state
                and hasattr(final_state, "steps")
                and len(final_state.steps) > 0
            ):
                analysis_step = final_state.steps[0].state.state
                if (
                    analysis_step
                    and hasattr(analysis_step, "final_result")
                    and analysis_step.final_result
                    and hasattr(analysis_step.final_result, "termination_output")
                ):
                    analysis_output = analysis_step.final_result.termination_output

                    # Extract source files information
                    if hasattr(analysis_output, "files_discovered"):
                        for file_info in analysis_output.files_discovered or []:
                            if isinstance(file_info, dict):
                                ui_data["file_manifest"]["source_files"].append(
                                    {
                                        "name": file_info.get("file", "unknown"),
                                        "path": file_info.get("full_path", ""),
                                        "size": file_info.get("size", "Unknown"),
                                        "type": file_info.get("kind", "ConfigMap"),
                                        "complexity": file_info.get(
                                            "complexity", "Medium"
                                        ),
                                    }
                                )

            # Get converted files from step results (YAML step) instead of final state
            # This ensures we use the actual source file names from the step execution
            yaml_step_results = step_results.get("YAML", {})
            if yaml_step_results and "final_result" in yaml_step_results:
                yaml_result = yaml_step_results["final_result"]

                # Check if we have converted files in the step results
                if isinstance(yaml_result, dict) and "converted_files" in yaml_result:
                    converted_files_data = yaml_result["converted_files"]

                    for converted_file_data in converted_files_data:
                        if isinstance(converted_file_data, dict):
                            ui_data["file_manifest"]["converted_files"].append(
                                {
                                    "source_file": converted_file_data.get(
                                        "source_file", ""
                                    ),
                                    "converted_file": converted_file_data.get(
                                        "converted_file", ""
                                    ),
                                    "conversion_status": converted_file_data.get(
                                        "conversion_status", "Success"
                                    ),
                                    "accuracy_rating": converted_file_data.get(
                                        "accuracy_rating", "95%"
                                    ),
                                    "file_type": converted_file_data.get(
                                        "file_type", "Azure Config"
                                    ),
                                    "azure_enhancements": converted_file_data.get(
                                        "azure_enhancements", []
                                    ),
                                    "concerns": converted_file_data.get("concerns", []),
                                    "download_url": f"/processes/{process_id}/converted/{converted_file_data.get('converted_file', '')}",
                                    "preview_available": True,
                                }
                            )

                    logger.info(
                        f"[UI-TELEMETRY] Extracted {len(converted_files_data)} converted files from YAML step results"
                    )
                else:
                    logger.warning(
                        "[UI-TELEMETRY] No converted_files found in YAML step results"
                    )

            # Fallback to final state if step results don't contain the data
            elif final_state and len(final_state.steps) > 2:
                logger.info("[UI-TELEMETRY] Using fallback method from final state")
                yaml_step = final_state.steps[2].state.state
                if yaml_step and hasattr(yaml_step, "converted_files"):
                    for converted_file in yaml_step.converted_files or []:
                        if hasattr(converted_file, "source_file"):
                            # Use the source file name from the converted file object
                            source_file_name = getattr(
                                converted_file, "source_file", ""
                            )

                            ui_data["file_manifest"]["converted_files"].append(
                                {
                                    "source_file": source_file_name,
                                    "converted_file": getattr(
                                        converted_file, "converted_file", ""
                                    ),
                                    "conversion_status": getattr(
                                        converted_file, "conversion_status", "Success"
                                    ),
                                    "accuracy_rating": getattr(
                                        converted_file, "accuracy_rating", "95%"
                                    ),
                                    "file_type": getattr(
                                        converted_file, "file_type", "Azure Config"
                                    ),
                                    "azure_enhancements": getattr(
                                        converted_file, "azure_enhancements", []
                                    ),
                                    "concerns": getattr(converted_file, "concerns", []),
                                    "download_url": f"/processes/{process_id}/converted/{getattr(converted_file, 'converted_file', '')}",
                                    "preview_available": True,
                                }
                            )

            # Get report files from Documentation step
            if final_outcome_data and "GeneratedFilesCollection" in final_outcome_data:
                collection = final_outcome_data["GeneratedFilesCollection"]
                for category, files in collection.items():
                    if isinstance(files, list):
                        for file_info in files:
                            if isinstance(file_info, dict) and "file_name" in file_info:
                                ui_data["file_manifest"]["report_files"].append(
                                    {
                                        "name": file_info["file_name"],
                                        "type": category.replace("_", " ").title(),
                                        "size": file_info.get(
                                            "file_size_estimate", "Unknown"
                                        ),
                                        "download_url": f"/processes/{process_id}/converted/{file_info['file_name']}",
                                        "content_summary": file_info.get(
                                            "content_summary", ""
                                        ),
                                    }
                                )

            # === NEW: Extract failed files with detailed reasons ===
            await self._extract_failed_files(ui_data, final_state, step_results)

        except Exception as e:
            logger.error(f"[UI-TELEMETRY] Failed to extract file manifest: {e}")

    async def _extract_failed_files(
        self, ui_data: dict, final_state: Any, step_results: dict[str, dict]
    ) -> None:
        """
        Extract detailed information about failed files for UI display.

        This method analyzes failure contexts from each step to provide
        comprehensive failure information including reasons, remediation
        suggestions, and retry capabilities.
        """
        try:
            failed_files = []

            # Track which files were processed vs failed to avoid duplicates
            processed_files = set()
            for converted in ui_data["file_manifest"]["converted_files"]:
                processed_files.add(converted.get("source_file", ""))

            # === Extract failures from each step ===
            step_names = ["Analysis", "Design", "YAML", "Documentation"]

            for step_name in step_names:
                step_data = step_results.get(step_name, {})

                # Check if step failed
                if not step_data.get("result", True):
                    failure_reason = step_data.get("reason", "Unknown failure")

                    # Extract step-specific failure details
                    if step_name == "Analysis":
                        failed_files.extend(
                            await self._extract_analysis_failures(
                                final_state, failure_reason, processed_files
                            )
                        )
                    elif step_name == "Design":
                        failed_files.extend(
                            await self._extract_design_failures(
                                final_state, failure_reason, processed_files
                            )
                        )
                    elif step_name == "YAML":
                        failed_files.extend(
                            await self._extract_yaml_failures(
                                final_state, failure_reason, processed_files
                            )
                        )
                    elif step_name == "Documentation":
                        failed_files.extend(
                            await self._extract_documentation_failures(
                                final_state, failure_reason, processed_files
                            )
                        )

            # === Extract failures from step failure contexts ===
            if final_state and hasattr(final_state, "steps"):
                for i, step in enumerate(final_state.steps):
                    if i < len(step_names):
                        step_name = step_names[i]
                        step_state = step.state.state

                        if (
                            step_state
                            and hasattr(step_state, "final_result")
                            and step_state.final_result
                            and hasattr(step_state.final_result, "termination_output")
                        ):
                            termination_output = (
                                step_state.final_result.termination_output
                            )

                            # Check for failure contexts in termination output
                            if hasattr(termination_output, "failure_contexts"):
                                for failure_context in (
                                    termination_output.failure_contexts or []
                                ):
                                    failed_file_info = (
                                        await self._process_failure_context(
                                            failure_context, step_name, processed_files
                                        )
                                    )
                                    if failed_file_info:
                                        failed_files.append(failed_file_info)

            # === Deduplicate and enrich failed files ===
            unique_failed_files = {}
            for failed_file in failed_files:
                source_file = failed_file.get("source_file", "unknown")
                if source_file not in unique_failed_files:
                    unique_failed_files[source_file] = failed_file
                else:
                    # Merge failure information if same file failed in multiple steps
                    existing = unique_failed_files[source_file]
                    existing["failure_steps"] = existing.get("failure_steps", []) + [
                        failed_file.get("failure_step", "")
                    ]
                    existing["technical_details"] += (
                        f"\n\n{failed_file.get('failure_step', '')} Step: {failed_file.get('technical_details', '')}"
                    )

            ui_data["file_manifest"]["failed_files"] = list(
                unique_failed_files.values()
            )

            logger.info(
                f"[UI-TELEMETRY] Extracted {len(unique_failed_files)} failed files with detailed reasons"
            )

        except Exception as e:
            logger.error(f"[UI-TELEMETRY] Failed to extract failed files: {e}")

    async def _extract_analysis_failures(
        self, final_state: Any, failure_reason: str, processed_files: set
    ) -> list[dict]:
        """Extract file failures from Analysis step."""
        try:
            failed_files = []

            # Get source files that couldn't be analyzed
            if (
                final_state
                and hasattr(final_state, "steps")
                and len(final_state.steps) > 0
            ):
                analysis_step = final_state.steps[0].state.state
                if (
                    analysis_step
                    and hasattr(analysis_step, "final_result")
                    and analysis_step.final_result
                    and hasattr(analysis_step.final_result, "termination_output")
                ):
                    analysis_output = analysis_step.final_result.termination_output

                    # Check for files that failed during analysis
                    if hasattr(analysis_output, "failed_files"):
                        for failed_file in analysis_output.failed_files or []:
                            source_file = failed_file.get("file", "unknown")
                            if source_file not in processed_files:
                                failed_files.append(
                                    {
                                        "source_file": source_file,
                                        "failure_step": "Analysis",
                                        "failure_reason": "File analysis failed",
                                        "failure_category": "parsing_error",
                                        "technical_details": failed_file.get(
                                            "error", failure_reason
                                        ),
                                        "remediation_suggestions": [
                                            "Check file syntax and format",
                                            "Ensure file is valid Kubernetes YAML",
                                            "Review file encoding and special characters",
                                        ],
                                        "retry_possible": True,
                                        "manual_fix_required": True,
                                        "severity": "high",
                                    }
                                )

            return failed_files

        except Exception as e:
            logger.error(f"[UI-TELEMETRY] Failed to extract analysis failures: {e}")
            return []

    async def _extract_design_failures(
        self, final_state: Any, failure_reason: str, processed_files: set
    ) -> list[dict]:
        """Extract file failures from Design step."""
        try:
            failed_files = []

            # Design failures are usually about compatibility or architectural constraints
            if (
                "compatibility" in failure_reason.lower()
                or "constraint" in failure_reason.lower()
            ):
                # These are typically architecture-level failures affecting multiple files
                failed_files.append(
                    {
                        "source_file": "multiple_files",
                        "failure_step": "Design",
                        "failure_reason": "Architecture compatibility issues",
                        "failure_category": "compatibility_issue",
                        "technical_details": failure_reason,
                        "remediation_suggestions": [
                            "Review Azure service compatibility matrix",
                            "Consider alternative Azure services",
                            "Modify application architecture for Azure compatibility",
                        ],
                        "retry_possible": False,
                        "manual_fix_required": True,
                        "severity": "critical",
                    }
                )

            return failed_files

        except Exception as e:
            logger.error(f"[UI-TELEMETRY] Failed to extract design failures: {e}")
            return []

    async def _extract_yaml_failures(
        self, final_state: Any, failure_reason: str, processed_files: set
    ) -> list[dict]:
        """Extract file failures from YAML conversion step."""
        try:
            failed_files = []

            # Get failed conversions from YAML step
            if final_state and len(final_state.steps) > 2:
                yaml_step = final_state.steps[2].state.state
                if yaml_step and hasattr(yaml_step, "converted_files"):
                    for converted_file in yaml_step.converted_files or []:
                        source_file = getattr(converted_file, "source_file", "")
                        conversion_status = getattr(
                            converted_file, "conversion_status", "Success"
                        )

                        if (
                            conversion_status.lower() != "success"
                            and source_file not in processed_files
                        ):
                            concerns = getattr(converted_file, "concerns", [])
                            failed_files.append(
                                {
                                    "source_file": source_file,
                                    "failure_step": "YAML",
                                    "failure_reason": f"Conversion failed: {conversion_status}",
                                    "failure_category": "conversion_error",
                                    "technical_details": "; ".join(concerns)
                                    if concerns
                                    else failure_reason,
                                    "remediation_suggestions": [
                                        "Review Kubernetes to Azure service mappings",
                                        "Check for unsupported resource configurations",
                                        "Consider manual conversion for complex resources",
                                    ],
                                    "retry_possible": True,
                                    "manual_fix_required": True,
                                    "severity": "medium",
                                }
                            )

            return failed_files

        except Exception as e:
            logger.error(f"[UI-TELEMETRY] Failed to extract YAML failures: {e}")
            return []

    async def _extract_documentation_failures(
        self, final_state: Any, failure_reason: str, processed_files: set
    ) -> list[dict]:
        """Extract file failures from Documentation step."""
        try:
            failed_files = []

            # Documentation failures are usually about report generation
            # These don't typically affect individual source files
            if failure_reason and "report" in failure_reason.lower():
                failed_files.append(
                    {
                        "source_file": "report_generation",
                        "failure_step": "Documentation",
                        "failure_reason": "Report generation failed",
                        "failure_category": "documentation_error",
                        "technical_details": failure_reason,
                        "remediation_suggestions": [
                            "Check output directory permissions",
                            "Verify template files are available",
                            "Review log files for detailed error information",
                        ],
                        "retry_possible": True,
                        "manual_fix_required": False,
                        "severity": "low",
                    }
                )

            return failed_files

        except Exception as e:
            logger.error(
                f"[UI-TELEMETRY] Failed to extract documentation failures: {e}"
            )
            return []

    async def _process_failure_context(
        self, failure_context: Any, step_name: str, processed_files: set
    ) -> dict | None:
        """Process individual failure context from step termination output."""
        try:
            if not failure_context:
                return None

            # Extract failure information based on failure context structure
            source_file = getattr(failure_context, "source_file", "unknown")
            error_message = getattr(failure_context, "error_message", "")
            severity = getattr(failure_context, "severity", "medium")

            if source_file in processed_files:
                return None  # Skip files that were successfully processed

            # Categorize failure based on error message
            failure_category = "unknown_error"
            remediation_suggestions = ["Review error details and retry"]

            if "syntax" in error_message.lower() or "parse" in error_message.lower():
                failure_category = "parsing_error"
                remediation_suggestions = [
                    "Check YAML syntax and indentation",
                    "Validate Kubernetes resource definitions",
                    "Fix any formatting issues",
                ]
            elif (
                "compatibility" in error_message.lower()
                or "unsupported" in error_message.lower()
            ):
                failure_category = "compatibility_issue"
                remediation_suggestions = [
                    "Review Azure service compatibility",
                    "Consider alternative Azure services",
                    "Update resource configuration for Azure",
                ]
            elif (
                "permission" in error_message.lower()
                or "access" in error_message.lower()
            ):
                failure_category = "access_error"
                remediation_suggestions = [
                    "Check file permissions",
                    "Verify access to source and output directories",
                    "Ensure proper authentication",
                ]

            return {
                "source_file": source_file,
                "failure_step": step_name,
                "failure_reason": error_message or "Unknown error occurred",
                "failure_category": failure_category,
                "technical_details": getattr(
                    failure_context, "technical_details", error_message
                ),
                "remediation_suggestions": remediation_suggestions,
                "retry_possible": severity.lower() != "critical",
                "manual_fix_required": True,
                "severity": severity.lower(),
            }

        except Exception as e:
            logger.error(f"[UI-TELEMETRY] Failed to process failure context: {e}")
            return None

    async def _calculate_dashboard_metrics(
        self, ui_data: dict, step_results: dict[str, dict]
    ) -> None:
        """Calculate dashboard metrics for UI display."""
        try:
            # Count files
            total_converted = len(ui_data["file_manifest"]["converted_files"])
            failed_files_count = len(ui_data["file_manifest"]["failed_files"])
            successful_files = len(
                [
                    f
                    for f in ui_data["file_manifest"]["converted_files"]
                    if f.get("conversion_status", "").lower() == "success"
                ]
            )

            # Total files processed = successful + failed
            total_processed = successful_files + failed_files_count

            # Calculate completion percentage based on step completion
            completed_steps = len(
                [r for r in step_results.values() if r.get("result", False)]
            )
            total_steps = len(step_results) if step_results else 4
            completion_percentage = (
                (completed_steps / total_steps * 100) if total_steps > 0 else 0
            )

            # Create comprehensive status summary
            if failed_files_count > 0:
                status_summary = f"Processed {total_processed} files: {successful_files} successful, {failed_files_count} failed"
            else:
                status_summary = (
                    f"Successfully converted {successful_files} of {total_converted} files"
                    if total_converted > 0
                    else "Migration completed successfully"
                )

            ui_data["dashboard_metrics"].update(
                {
                    "completion_percentage": completion_percentage,
                    "files_processed": total_processed,
                    "files_successful": successful_files,
                    "files_failed": failed_files_count,
                    "status_summary": status_summary,
                }
            )

            logger.info(
                f"[UI-TELEMETRY] Dashboard metrics - "
                f"Total: {total_processed}, Successful: {successful_files}, Failed: {failed_files_count}"
            )

        except Exception as e:
            logger.error(f"[UI-TELEMETRY] Failed to calculate dashboard metrics: {e}")

    async def _build_step_progress(
        self, ui_data: dict, step_results: dict[str, dict], final_state: Any
    ) -> None:
        """Build step progress information for UI timeline."""
        try:
            step_names = ["Analysis", "Design", "YAML", "Documentation"]

            for step_name in step_names:
                step_data = step_results.get(step_name, {})
                status = "completed" if step_data.get("result", False) else "failed"

                logger.debug(
                    f"[UI-TELEMETRY] Building progress for {step_name} - Status: {status}"
                )

                step_info = {
                    "step_name": step_name,
                    "status": status,
                    "duration": "Unknown",  # Could be calculated from telemetry
                    "key_findings": [],
                }

                # Add step-specific details
                if step_name == "Analysis" and step_data.get("termination_output"):
                    termination = step_data["termination_output"]
                    files_discovered = getattr(termination, "files_discovered", [])
                    files_count = len(files_discovered) if files_discovered else 0
                    source_platform = getattr(termination, "source_platform", "Unknown")
                    step_info["files_analyzed"] = files_count
                    step_info["key_findings"] = [
                        f"Analyzed {files_count} configuration files",
                        f"Platform: {source_platform}",
                    ]
                elif step_name == "Design" and step_data.get("termination_output"):
                    termination = step_data["termination_output"]
                    design_elements = getattr(termination, "design_elements", [])
                    step_info["design_elements_count"] = (
                        len(design_elements) if design_elements else 0
                    )
                    step_info["key_findings"] = [
                        f"Created {len(design_elements)} design elements"
                        if design_elements
                        else "Design phase completed"
                    ]
                elif step_name == "YAML" and step_data.get("termination_output"):
                    converted_count = len(ui_data["file_manifest"]["converted_files"])
                    step_info["files_converted"] = converted_count
                    step_info["key_findings"] = [
                        f"Converted {converted_count} files to Azure format"
                    ]
                elif step_name == "Documentation" and step_data.get(
                    "termination_output"
                ):
                    termination = step_data["termination_output"]
                    reports_generated = getattr(termination, "reports_generated", [])
                    step_info["reports_count"] = (
                        len(reports_generated) if reports_generated else 0
                    )
                    step_info["key_findings"] = [
                        f"Generated {len(reports_generated)} documentation files"
                        if reports_generated
                        else "Documentation phase completed"
                    ]

                ui_data["step_progress"].append(step_info)

            logger.info(
                f"[UI-TELEMETRY] Built step progress for {len(step_names)} steps"
            )

        except Exception as e:
            logger.error(f"[UI-TELEMETRY] Failed to build step progress: {e}")

    async def _collect_downloadable_artifacts(
        self, ui_data: dict, final_outcome_data: dict, process_id: str
    ) -> None:
        """Collect all downloadable artifacts for UI download section."""
        try:
            # Converted configuration files
            ui_data["downloadable_artifacts"]["converted_configs"] = [
                f["download_url"]
                for f in ui_data["file_manifest"]["converted_files"]
                if f.get("download_url")
            ]

            # Report and documentation files
            ui_data["downloadable_artifacts"]["reports"] = [
                f["download_url"]
                for f in ui_data["file_manifest"]["report_files"]
                if f.get("type", "").lower()
                in ["executive summary", "technical analysis"]
            ]

            ui_data["downloadable_artifacts"]["documentation"] = [
                f["download_url"]
                for f in ui_data["file_manifest"]["report_files"]
                if f.get("type", "").lower()
                in ["deployment guide", "migration documentation"]
            ]

            # Archive could be generated on-demand
            if ui_data["downloadable_artifacts"]["converted_configs"]:
                ui_data["downloadable_artifacts"]["archive"] = (
                    f"/{process_id}/converted/complete_migration_package.zip"
                )

        except Exception as e:
            logger.error(
                f"[UI-TELEMETRY] Failed to collect downloadable artifacts: {e}"
            )


async def create_migration_service(
    app_context: Any | None = None,
    debug_mode: bool = False,
    timeout_minutes: int = 25,
    **kwargs,
) -> MigrationProcessor:
    """
    Factory function to create and initialize a migration processor

    Following Microsoft Content Processing Solution Accelerator patterns for
    enterprise queue-based processing with proper initialization and configuration.

    Args:
        app_context: Application context for telemetry and configuration
        debug_mode: Enable debug logging and detailed telemetry
        timeout_minutes: Process timeout in minutes for circuit breaker
        **kwargs: Additional configuration passed to kernel agent

    Returns:
        Initialized MigrationProcessor instance ready for queue processing

    Raises:
        RuntimeError: If processor initialization fails
    """
    processor = MigrationProcessor(
        app_context=app_context, debug_mode=debug_mode, timeout_minutes=timeout_minutes
    )

    await processor.initialize(**kwargs)
    return processor
