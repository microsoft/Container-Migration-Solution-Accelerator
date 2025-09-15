from agents.agent_info_util import MigrationPhase, load_prompt_text
from utils.agent_builder import AgentType, agent_info


def get_agent_info(phase: MigrationPhase | str | None = None) -> agent_info:
    """Get QA Engineer agent info with optional phase-specific prompt.

    Args:
        phase (MigrationPhase | str | None): Migration phase ('analysis', 'design', 'yaml', 'documentation').
                              If provided, loads phase-specific prompt.
    """
    return agent_info(
        agent_name="QA_Engineer",
        agent_type=AgentType.ChatCompletionAgent,
        agent_description="QA Engineer specializing in AKS (Azure Kubernetes Service) migration quality inspection and testing.",
        agent_instruction=load_prompt_text(phase=phase),
    )

    # "Refresh tools what you can use"
    # "This is Phase goal and descriptions to complete the migration. - {{prompt}}"
    # "You are a Quality Assurance expert providing comprehensive and precise AKS migration quality inspection and testing. "
    # "Your expertise is grounded in the Azure Well-Architected Framework (WAF), and all QA activities should align with its principles. "
    # "As a senior QA engineer, you bring extensive experience with cloud-native applications and deep knowledge of AKS migration from other cloud platforms. "
    # "You excel in cross-functional collaboration and stakeholder communication. "
    # "You maintain current knowledge of industry trends and best practices. "
    # "In collaborative discussions, you engage constructively and challenge ideas respectfully when necessary."


# class AgentInfo:
#     agent_name: str = "QA_Engineer"
#     agent_type: AgentType = AgentType.ChatCompletionAgent
#     agent_system_prompt: str = load_prompt_text("./prompt4.txt")
#     agent_instruction: str = "You are an expert in QA (Quality Assurance). providing detailed and accurate AKS migration quality inspection and testing."
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
