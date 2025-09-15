# Color and icon utility functions for enhanced display
from semantic_kernel.contents.utils.author_role import AuthorRole


class ConsoleColors:
    """ANSI color codes for terminal output"""

    # Colors
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"

    # Styles
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"

    # Background colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


def get_role_style(role, name=None):
    """Get color, icon, and formatting for different roles and agents"""

    # Role-based styling
    if role == AuthorRole.USER:
        return (
            f"{ConsoleColors.BOLD}{ConsoleColors.BLUE}[USER] USER{ConsoleColors.RESET}",
            ConsoleColors.BLUE,
        )
    elif role == AuthorRole.ASSISTANT:
        # Agent-specific styling
        agent_styles = {
            "Technical_Architect": (
                f"{ConsoleColors.BOLD}{ConsoleColors.MAGENTA}[BUILDING]  Chief Architect{ConsoleColors.RESET}",
                ConsoleColors.MAGENTA,
            ),
            "GKE_Expert": (
                f"{ConsoleColors.BOLD}{ConsoleColors.GREEN}[CLOUD]  GKE EXPERT{ConsoleColors.RESET}",
                ConsoleColors.GREEN,
            ),
            "EKS_Expert": (
                f"{ConsoleColors.BOLD}{ConsoleColors.YELLOW}[CLOUD]  EKS EXPERT{ConsoleColors.RESET}",
                ConsoleColors.YELLOW,
            ),
            "Azure_Expert": (
                f"{ConsoleColors.BOLD}{ConsoleColors.CYAN}[CLOUD]  AZURE EXPERT{ConsoleColors.RESET}",
                ConsoleColors.CYAN,
            ),
            "YAML_Expert": (
                f"{ConsoleColors.BOLD}{ConsoleColors.WHITE}[NOTES] YAML EXPERT{ConsoleColors.RESET}",
                ConsoleColors.WHITE,
            ),
            # "Azure_Network_Engineer": (
            #     f"{ConsoleColors.BOLD}{ConsoleColors.BLUE}[GLOBE] NETWORK ENGINEER{ConsoleColors.RESET}",
            #     ConsoleColors.BLUE,
            # ),
            # "Azure_Security_Engineer": (
            #     f"{ConsoleColors.BOLD}{ConsoleColors.RED}[LOCK] SECURITY ENGINEER{ConsoleColors.RESET}",
            #     ConsoleColors.RED,
            # ),
            # "Azure_DevOps_Engineer": (
            #     f"{ConsoleColors.BOLD}{ConsoleColors.GREEN}[CONFIG]  DEVOPS ENGINEER{ConsoleColors.RESET}",
            #     ConsoleColors.GREEN,
            # ),
            # "Azure_Storage_Engineer": (
            #     f"{ConsoleColors.BOLD}{ConsoleColors.YELLOW}[SAVE] STORAGE ENGINEER{ConsoleColors.RESET}",
            #     ConsoleColors.YELLOW,
            # ),
            "Technical_Writer": (
                f"{ConsoleColors.BOLD}{ConsoleColors.MAGENTA}[BOOKS] TECHNICAL WRITER{ConsoleColors.RESET}",
                ConsoleColors.MAGENTA,
            ),
            "QA_Engineer": (
                f"{ConsoleColors.BOLD}{ConsoleColors.CYAN}[SUCCESS] QA ENGINEER{ConsoleColors.RESET}",
                ConsoleColors.CYAN,
            ),
        }

        if name and name in agent_styles:
            return agent_styles[name]
        else:
            return (
                f"{ConsoleColors.BOLD}{ConsoleColors.WHITE}[ROBOT] ASSISTANT{ConsoleColors.RESET}",
                ConsoleColors.WHITE,
            )
    else:
        return (
            f"{ConsoleColors.GRAY}[QUESTION] {role.upper()}{ConsoleColors.RESET}",
            ConsoleColors.GRAY,
        )


def format_agent_message(role, name, content, max_content_length=200):
    """Format agent message with colors, icons and truncation"""
    role_display, content_color = get_role_style(role, name)
    content_display = f"{content_color}{content}{ConsoleColors.RESET}"

    return f"# {role_display}: {content_display}"
