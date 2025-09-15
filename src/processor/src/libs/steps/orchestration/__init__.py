"""
Orchestration Package

This package contains specialized orchestration modules for different steps
in the Azure Kubernetes migration process. Each module provides focused
functionality for its respective step type.

Modules:
    base_orchestrator: Common base classes and utilities
    analysis_orchestration: Analysis step orchestration
    design_orchestration: Design step orchestration
    yaml_orchestration: YAML step orchestration
    documentation_orchestration: Documentation step orchestration

Classes exported for public use:
    - StepGroupChatOrchestrator: Base factory class
    - StepSpecificGroupChatManager: Base manager class
    - AnalysisOrchestrator: Analysis step factory
    - AnalysisStepGroupChatManager: Analysis step manager
    - DesignOrchestrator: Design step factory
    - DesignStepGroupChatManager: Design step manager
    - YamlOrchestrator: YAML step factory
    - YamlStepGroupChatManager: YAML step manager
    - DocumentationOrchestrator: Documentation step factory
    - DocumentationStepGroupChatManager: Documentation step manager
"""

# Base classes
# Analysis orchestration
from .analysis_orchestration import (
    AnalysisOrchestrator,
    AnalysisStepGroupChatManager,
)
from .base_orchestrator import (
    StepGroupChatOrchestrator,
    StepSpecificGroupChatManager,
)

# Design orchestration
from .design_orchestration import (
    DesignOrchestrator,
    DesignStepGroupChatManager,
)

# Documentation orchestration
from .documentation_orchestration import (
    DocumentationOrchestrator,
    DocumentationStepGroupChatManager,
)

# YAML orchestration
from .yaml_orchestration import (
    YamlOrchestrator,
    YamlStepGroupChatManager,
)

__all__ = [
    # Base classes
    "StepGroupChatOrchestrator",
    "StepSpecificGroupChatManager",
    # Analysis
    "AnalysisOrchestrator",
    "AnalysisStepGroupChatManager",
    # Design
    "DesignOrchestrator",
    "DesignStepGroupChatManager",
    # YAML
    "YamlOrchestrator",
    "YamlStepGroupChatManager",
    # Documentation
    "DocumentationOrchestrator",
    "DocumentationStepGroupChatManager",
]
