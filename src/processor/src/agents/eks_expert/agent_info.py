from agents.agent_info_util import MigrationPhase, load_prompt_text
from utils.agent_builder import AgentType, agent_info

# class AgentInfo(agent_info):
#     agent_name = "EKS_Expert"
#     agent_type = AgentType.ChatCompletionAgent
#     agent_instruction = "You are an expert in EKS (Amazon Elastic Kubernetes Service). providing detailed and accurate information"
#     agent_system_prompt = load_prompt_text("./prompt3.txt")


def get_agent_info(phase: MigrationPhase | str | None = None) -> agent_info:
    """Get EKS Expert agent info with optional phase-specific prompt.

    Args:
        phase (str | None): Migration phase ('analysis', 'design', 'yaml', 'documentation').
                              If provided, loads phase-specific prompt.
    """
    return agent_info(
        agent_name="EKS_Expert",
        agent_type=AgentType.ChatCompletionAgent,
        agent_description="Amazon Web Services cloud architect specializing in Elastic Kubernetes Service (EKS) with expertise in Kubernetes migration initiatives.",
        agent_instruction=load_prompt_text(phase=phase),
    )

    # "Refresh tools what you can use"
    # "This is Phase goal and descriptions to complete the migration. - {{prompt}}"
    # "You are a specialist in Amazon Elastic Kubernetes Service (EKS), delivering comprehensive and precise guidance."
    # "You are a veteran EKS migration expert, with a deep understanding of Kubernetes and cloud-native architectures."
    # "You have strong experience in AKS (Azure Kubernetes Service) and its integration with EKS."
    # "You possess strong communication skills to collaborate with cross-functional teams and stakeholders."
    # "You are committed to staying updated with the latest industry trends and best practices."
    # "You are in a debate. Feel free to challenge the other participants with respect."
