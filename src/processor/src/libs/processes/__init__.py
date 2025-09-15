"""
Process Framework for Azure Migration with 4-Phase Workflow

This module provides a structured Process Framework that integrates with
Semantic Kernel Process Framework and existing Group Chat Orchestration
for Azure Kubernetes Service (AKS) migration workflows.

Key Features:
- 4-Phase Migration Process (Analysis, Design, YAML, Documentation)
- Quality Gates with QA Engineer validation
- Retry mechanisms for phase and quality gate failures
- Pydantic models for robust type safety and validation
- Integration with existing MCP context and agent infrastructure
"""

# Currently available models
from .models.migration_state import (
    AnalysisStepResult,
    DesignStepResult,
    DocumentationStepResult,
    MigrationProcessState,
    YamlStepResult,
)

# TODO: Uncomment these imports once the additional modules are created
# from .models import (
#     MigrationPhase,
#     PhaseResult,
#     ProcessContext,
#     ProcessExecutionResult,
#     QualityGateResult,
#     QualityValidationResult,
# )
# from .orchestration import CompletionStep
# from .phases import (
#     AnalysisPhaseStep,
#     DesignPhaseStep,
#     DocumentationPhaseStep,
#     YamlPhaseStep,
# )
# from .quality_gates import QualityGateValidationStep, RetryCoordinatorStep

__all__ = [
    # Models currently available
    "MigrationProcessState",
    "AnalysisStepResult",
    "DesignStepResult",
    "YamlStepResult",
    "DocumentationStepResult",
    # TODO: Uncomment these once the corresponding modules are created
    # "MigrationPhase",
    # "QualityGateResult",
    # "ProcessContext",
    # "PhaseResult",
    # "QualityValidationResult",
    # "ProcessExecutionResult",
    # "AnalysisPhaseStep",
    # "DesignPhaseStep",
    # "YamlPhaseStep",
    # "DocumentationPhaseStep",
    # "QualityGateValidationStep",
    # "RetryCoordinatorStep",
    # "CompletionStep",
]
