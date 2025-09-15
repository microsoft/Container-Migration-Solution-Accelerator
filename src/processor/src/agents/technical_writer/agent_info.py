from agents.agent_info_util import MigrationPhase, load_prompt_text
from utils.agent_builder import AgentType, agent_info


def get_agent_info(phase: MigrationPhase | str | None = None) -> agent_info:
    """Get Technical Writer agent info with optional phase-specific prompt.

    Args:
        phase (MigrationPhase | str | None): Migration phase ('analysis', 'design', 'yaml', 'documentation').
                              If provided, loads phase-specific prompt.
    """
    return agent_info(
        agent_name="Technical_Writer",
        agent_type=AgentType.ChatCompletionAgent,
        agent_description="Technical Writer specializing in Kubernetes migration documentation.",
        agent_instruction=load_prompt_text(phase=phase),
    )

    # "Refresh tools what you can use"
    # "This is Phase goal and descriptions to complete the migration. - {{prompt}}"
    # "You are a technical writer specializing in Kubernetes documentation. Create clear and concise documentation for Kubernetes resources, including YAML manifests, Helm charts, and API references. "
    # "You have very deep technical understanding and can provide detailed explanations and insights into complex topics."
    # "You write technical documentation that is accurate, thorough, and easy to understand."
    # "You use best practices from project teams migration process and outputs to generating detail migration result document."
    # "You possess strong communication skills to collaborate with cross-functional teams and stakeholders."
    # "You are committed to staying updated with the latest industry trends and best practices."
    # "You are in a debate. Feel free to challenge the other participants with respect."


# class AgentInfo:
#     agent_name: str = "Technical_Writer"
#     agent_type: AgentType = AgentType.ChatCompletionAgent
#     agent_system_prompt: str = load_prompt_text("./prompt3.txt")
#     agent_instruction: str = "You are a technical writer specializing in Kubernetes documentation. Create clear and concise documentation for Kubernetes resources, including YAML manifests, Helm charts, and API references."
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
