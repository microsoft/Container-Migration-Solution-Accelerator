from agents.agent_info_util import MigrationPhase, load_prompt_text
from utils.agent_builder import AgentType, agent_info


def get_agent_info(phase: MigrationPhase | str | None = None) -> agent_info:
    """Get Chief Architect agent info with optional phase-specific prompt.

    Args:
        phase (MigrationPhase | str | None): Migration phase (enum preferred).
                                           If provided, loads phase-specific prompt.
    """
    return agent_info(
        agent_name="Chief_Architect",
        agent_type=AgentType.ChatCompletionAgent,
        agent_description="Chief Architect leading Azure Cloud Kubernetes migration project",
        agent_instruction=load_prompt_text(phase=phase),
    )
