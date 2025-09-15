from enum import Enum
import inspect
from pathlib import Path


class MigrationPhase(str, Enum):
    """Enumeration of migration phases for type safety and consistency."""

    ANALYSIS = "analysis"
    DESIGN = "design"
    YAML = "yaml"
    DOCUMENTATION = "documentation"

    # Incident Response Writer specialized phases
    FAILURE_ANALYSIS = "failure-analysis"
    STAKEHOLDER_COMMUNICATION = "stakeholder-communication"
    RECOVERY_PLANNING = "recovery-planning"
    RETRY_ANALYSIS = "retry-analysis"


def load_prompt_text(phase: MigrationPhase | str | None = None) -> str:
    """
    Load the appropriate prompt text based on the migration phase.

    Args:
        phase (MigrationPhase | str | None): Migration phase (MigrationPhase enum or string).
                                           If None, loads the default prompt.

    Returns:
        str: The content of the appropriate prompt file.
    """
    # Convert phase to string value if it's an enum
    if isinstance(phase, MigrationPhase):
        phase_str = phase.value
    elif isinstance(phase, str):
        phase_str = phase.lower()
    else:
        phase_str = None

    # Determine the prompt filename based on phase
    if phase_str and phase_str in [p.value for p in MigrationPhase]:
        prompt_filename = f"prompt-{phase_str}.txt"
    else:
        # No phase specified or invalid phase, use default
        prompt_filename = "prompt.txt"

    # Get the directory of the calling agent (e.g., technical_architect/)
    current_frame = inspect.currentframe()
    if current_frame is None or current_frame.f_back is None:
        raise RuntimeError("Unable to determine caller's file location")

    caller_frame = current_frame.f_back
    caller_file = Path(caller_frame.f_code.co_filename)
    agent_directory = caller_file.parent
    prompt_path = agent_directory / prompt_filename

    with open(prompt_path, encoding="utf-8") as file:
        return file.read().strip()
