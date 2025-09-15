from agents.agent_info_util import MigrationPhase, load_prompt_text
from utils.agent_builder import AgentType, agent_info

# class AgentInfo(agent_info):
#     agent_name = "Azure_Expert"
#     agent_type = AgentType.ChatCompletionAgent
#     agent_system_prompt = load_prompt_text("./prompt3.txt")
#     agent_instruction = "You are an expert in Azure services, providing detailed and accurate information."


def get_agent_info(phase: MigrationPhase | str | None = None) -> agent_info:
    """Get Azure Expert agent info with optional phase-specific prompt.

    Args:
        phase (str | None): Migration phase ('analysis', 'design', 'yaml', 'documentation').
                              If provided, loads phase-specific prompt.
    """
    return agent_info(
        agent_name="Azure_Expert",
        agent_type=AgentType.ChatCompletionAgent,
        agent_description="Azure Cloud Service Expert participating in Azure Cloud Kubernetes migration project",
        agent_instruction=load_prompt_text(phase=phase),
    )
    # "Refresh tools what you can use"
    # "This is Phase goal and descriptions to complete the migration. - {{prompt}}"
    # "You are an expert in Azure services, providing detailed and accurate information."
    # "You are veteran Azure Kubernetes Migration from GKE or EKS projects."
    # "You are very knowledgeable about mapping Amazon Web Services (AWS) or Google Cloud Platform (GCP) to Azure."
    # "You have a deep understanding of Azure's architecture and services."
    # "You are fluent in Azure WAF(Well-Architected Framework) and best practices for design on Azure."
    # "You have very flexible and smart communication skills to work with project staffs and stakeholders."
    # "You are in a debate. Feel free to challenge the other participants with respect."
