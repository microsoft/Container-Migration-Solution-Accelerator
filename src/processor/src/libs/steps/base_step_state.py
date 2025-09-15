import time

from pydantic import Field
from semantic_kernel.processes.kernel_process import (
    KernelProcessStepState,
)

from libs.models.failure_context import StepFailureState


class BaseStepState(KernelProcessStepState):
    # Base fields required by KernelProcessStepState
    name: str = Field(default="BaseStepState", description="Name of the step state")
    version: str = Field(default="1.0", description="Version of the step state")

    # NEW: Rich failure context for unhappy path
    failure_context: StepFailureState | None = Field(
        default=None, description="Rich failure context when step fails"
    )

    # NEW: Comprehensive timing infrastructure for failure context
    execution_start_time: float | None = Field(
        default=None, description="When step execution started"
    )
    execution_end_time: float | None = Field(
        default=None, description="When step execution completed"
    )
    orchestration_start_time: float | None = Field(
        default=None, description="When orchestration phase started"
    )
    orchestration_end_time: float | None = Field(
        default=None, description="When orchestration phase ended"
    )
    setup_duration: float | None = Field(
        default=None,
        description="Duration between execution start and orchestration start (seconds)",
    )
    orchestration_duration: float | None = Field(
        default=None, description="Duration of orchestration phase (seconds)"
    )
    total_execution_duration: float | None = Field(
        default=None, description="Total duration from start to end (seconds)"
    )

    def set_execution_start(self) -> None:
        """Set execution start time to current timestamp."""
        self.execution_start_time = time.time()

    def set_orchestration_start(self) -> None:
        """Set orchestration start time and calculate setup duration."""
        self.orchestration_start_time = time.time()
        if self.execution_start_time is not None:
            self.setup_duration = (
                self.orchestration_start_time - self.execution_start_time
            )

    def set_orchestration_end(self) -> None:
        """Set orchestration end time and calculate orchestration duration."""
        self.orchestration_end_time = time.time()
        if self.orchestration_start_time is not None:
            self.orchestration_duration = (
                self.orchestration_end_time - self.orchestration_start_time
            )

    def set_execution_end(self) -> None:
        """Set execution end time and calculate total duration."""
        self.execution_end_time = time.time()
        if self.execution_start_time is not None:
            self.total_execution_duration = (
                self.execution_end_time - self.execution_start_time
            )

    def get_timing_summary(self) -> dict[str, float | None]:
        """Get comprehensive timing summary for failure context."""
        return {
            "execution_start_time": self.execution_start_time,
            "execution_end_time": self.execution_end_time,
            "orchestration_start_time": self.orchestration_start_time,
            "orchestration_end_time": self.orchestration_end_time,
            "setup_duration": self.setup_duration,
            "orchestration_duration": self.orchestration_duration,
            "total_execution_duration": self.total_execution_duration,
        }
