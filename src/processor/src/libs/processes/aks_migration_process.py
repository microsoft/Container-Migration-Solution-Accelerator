"""
Migration Process Definition following SK Process Framework Best Practices.

This module defines the main migration process using the recommended structure:
- Single responsibility principle
- Proper event handling with comprehensive error collection
- Kernel isolation
- Clear process flow
- Batch processing error management
"""

from semantic_kernel.processes import ProcessBuilder

from libs.steps.analysis_step import AnalysisStep
from libs.steps.design_step import DesignStep
from libs.steps.documentation_step import DocumentationStep

# from libs.steps.error_handler_step import ErrorHandlerStep
# from libs.steps.event_sink_step import EventSinkHandlerStep
from libs.steps.yaml_step import YamlStep


class AKSMigrationProcess:
    """
    Main migration process following SK Process Framework best practices.

    Process Flow:
    Analysis → Design → YAML Generation → Documentation

    Each step is isolated and communicates via events only.
    """

    @staticmethod
    def create_process():
        """
        Create the migration process with proper event routing and telemetry support.

        Following best practices:
        - Each step has single responsibility
        - Events handle all inter-step communication
        - Error handling at each step
        - Clear process boundaries
        - Telemetry integration for monitoring
        """

        # Create ProcessBuilder with required parameters
        process_builder = ProcessBuilder(name="AKSMigrationProcess")

        # Use default constructors
        analysis_step = process_builder.add_step(AnalysisStep)
        design_step = process_builder.add_step(DesignStep)
        yaml_step = process_builder.add_step(YamlStep)
        documentation_step = process_builder.add_step(DocumentationStep)

        # event_sink_step = process_builder.add_step(EventSinkHandlerStep)
        # error_handler_step = process_builder.add_step(ErrorHandlerStep)

        # CRITICAL: Route initial StartMigration event to first step
        process_builder.on_input_event("StartMigration").send_event_to(
            target=analysis_step,
            function_name="start_migration_analysis",
            parameter_name="context_data",
        )

        # Analysis triggers Design when completed
        analysis_step.on_event("AnalysisCompleted").send_event_to(
            target=design_step,
            function_name="start_design_from_analysis",
            parameter_name="context_data",
        )

        # Design triggers YAML when completed
        design_step.on_event("DesignCompleted").send_event_to(
            target=yaml_step,
            function_name="start_yaml_from_design",
            parameter_name="context_data",
        )

        # YAML triggers Documentation when completed
        yaml_step.on_event("YamlCompleted").send_event_to(
            target=documentation_step,
            function_name="start_documentation_from_yaml",
            parameter_name="context_data",
        )

        # Documentation completion - process ends naturally
        # The SK Process Framework will detect completion when no more events are generated
        # Documentation step completes without emitting further events

        # ERROR HANDLING - Route all step failure events to error handler
        # FIXED: Use correct event name "handle_step_failure" (not "on_step_failed")
        # analysis_step.on_event("handle_step_failure").send_event_to(
        #     target=error_handler_step,
        #     function_name="on_step_failed",
        #     parameter_name="error_data",
        # )

        # design_step.on_event("handle_step_failure").send_event_to(
        #     target=error_handler_step,
        #     function_name="on_step_failed",
        #     parameter_name="error_data",
        # )

        # yaml_step.on_event("handle_step_failure").send_event_to(
        #     target=error_handler_step,
        #     function_name="on_step_failed",
        #     parameter_name="error_data",
        # )

        # documentation_step.on_event("handle_step_failure").send_event_to(
        #     target=error_handler_step,
        #     function_name="on_step_failed",
        #     parameter_name="error_data",
        # )

        # # Event Sink from each steps
        # analysis_step.on_event("OnStateChange").send_event_to(
        #     target=event_sink_step,
        #     function_name="on_state_change",
        #     parameter_name="event_data",
        # )

        # design_step.on_event("OnStateChange").send_event_to(
        #     target=event_sink_step,
        #     function_name="on_state_change",
        #     parameter_name="event_data",
        # )

        # yaml_step.on_event("OnStateChange").send_event_to(
        #     target=event_sink_step,
        #     function_name="on_state_change",
        #     parameter_name="event_data",
        # )

        # documentation_step.on_event("OnStateChange").send_event_to(
        #     target=event_sink_step,
        #     function_name="on_state_change",
        #     parameter_name="event_data",
        # )

        # # Hard Termination process from ALL steps (not just Analysis)
        # analysis_step.on_event("on_step_terminated_with_hard").send_event_to(
        #     target=error_handler_step,
        #     function_name="on_step_terminated_with_hard",
        #     parameter_name="termination_data",
        # )

        # design_step.on_event("on_step_terminated_with_hard").send_event_to(
        #     target=error_handler_step,
        #     function_name="on_step_terminated_with_hard",
        #     parameter_name="termination_data",
        # )

        # yaml_step.on_event("on_step_terminated_with_hard").send_event_to(
        #     target=error_handler_step,
        #     function_name="on_step_terminated_with_hard",
        #     parameter_name="termination_data",
        # )

        # documentation_step.on_event("on_step_terminated_with_hard").send_event_to(
        #     target=error_handler_step,
        #     function_name="on_step_terminated_with_hard",
        #     parameter_name="termination_data",
        # )

        # ERROR HANDLING COMPLETED - All migration errors are now handled by sophisticated
        # step-level error handling with 3-tier classification (IGNORABLE/RETRYABLE/CRITICAL)
        # Each step (Analysis, Design, YAML, Documentation) has its own error handling capability

        # SIMPLIFIED UNHAPPY PATH: No DocumentationWithErrors routing
        # Steps set failure state directly, Migration Service handles all failure reporting

        return process_builder.build()
