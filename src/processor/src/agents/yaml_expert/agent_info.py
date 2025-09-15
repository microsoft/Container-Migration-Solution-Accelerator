from agents.agent_info_util import MigrationPhase, load_prompt_text
from utils.agent_builder import AgentType, agent_info


def get_agent_info(phase: MigrationPhase | str | None = None) -> agent_info:
    """Get YAML Expert agent info with optional phase-specific prompt.

    Args:
        phase (MigrationPhase | str | None): Migration phase ('analysis', 'design', 'yaml', 'documentation').
                              If provided, loads phase-specific prompt.
    """
    return agent_info(
        agent_name="YAML_Expert",
        agent_type=AgentType.ChatCompletionAgent,
        agent_description="YAML Expert specializing in Kubernetes YAML in GKE, EKS, and AKS.",
        agent_instruction=load_prompt_text(phase=phase),
    )

    # "Refresh tools what you can use"
    # "This is Phase goal and descriptions to complete the migration. - {{prompt}}"
    # "You are an expert in Kubernetes YAML in GKE, EKS and AKS. Provide detailed and accurate information about YAML file conversion between these platforms."
    # "You have many complex Azure Kubernetes migration experiences."
    # "You have a deep understanding of YAML syntax and best practices."
    # "You possess strong communication skills to collaborate with cross-functional teams and stakeholders."
    # "You are committed to staying updated with the latest industry trends and best practices."
    # "You are in a debate. Feel free to challenge the other participants with respect."


# class AgentInfo:
#     agent_name: str = "YAML_Expert"
#     agent_type: AgentType = AgentType.ChatCompletionAgent
#     agent_system_prompt: str = load_prompt_text("./prompt4.txt")
#     agent_instruction: str = "You are an expert in Kubernetes YAML in GKE, EKS and AKS. Provide detailed and accurate information about YAML file conversion between these platforms."
# @staticmethod
# def system_prompt(
#     source_file_folder: str,
#     output_file_folder: str,
#     workplace_file_folder: str,
#     container_name: str | None = None,
# ) -> str:
#     system_prompt: Template = Template(load_prompt_text("./prompt4.txt"))
#     return system_prompt.render(
#         source_file_folder=source_file_folder,
#         output_file_folder=output_file_folder,
#         workplace_file_folder=workplace_file_folder,
#         container_name=container_name,
#     )
