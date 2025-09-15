from agents.agent_info_util import MigrationPhase, load_prompt_text
from utils.agent_builder import AgentType, agent_info


def get_agent_info(phase: MigrationPhase | str | None = None) -> agent_info:
    """Get GKE Expert agent info with optional phase-specific prompt.

    Args:
        phase (MigrationPhase | str | None): Migration phase ('analysis', 'design', 'yaml', 'documentation').
                              If provided, loads phase-specific prompt.
    """
    return agent_info(
        agent_name="GKE_Expert",
        agent_type=AgentType.ChatCompletionAgent,
        agent_description="Google Cloud Platform architect specializing in Google Kubernetes Engine (GKE) with expertise in Kubernetes migration initiatives.",
        agent_instruction=load_prompt_text(phase=phase),
    )

    # "Refresh tools what you can use"
    # "This is Phase goal and descriptions to complete the migration. - {{prompt}}"
    # "You are an expert in GKE (Google Kubernetes Engine).  delivering comprehensive and precise guidance."
    # "You are a veteran GKE migration expert, with a deep understanding of Kubernetes and cloud-native architectures."
    # "You have strong experience in AKS (Azure Kubernetes Service) and its integration with GKE."
    # "You possess strong communication skills to collaborate with cross-functional teams and stakeholders."
    # "You are committed to staying updated with the latest industry trends and best practices."
    # "You are in a debate. Feel free to challenge the other participants with respect."


# class AgentInfo:
#     agent_name = "GKE_Expert"
#     agent_type = AgentType.ChatCompletionAgent
#     agent_system_prompt = load_prompt_text("./prompt4.txt")
#     agent_instruction = "You are an expert in GKE (Google Kubernetes Engine). providing detailed and accurate information"
# @staticmethod
# def system_prompt(
#     source_file_folder: str,
#     output_file_folder: str,
#     workplace_file_folder: str,
#     container_name: str | None = None,
# ) -> str:
#     system_prompt: Template = Template(load_prompt_text("./prompt3.txt"))
#     return system_prompt.render(
#         source_file_folder=source_file_folder,
#         output_file_folder=output_file_folder,
#         workplace_file_folder=workplace_file_folder,
#         container_name=container_name,
#     )
