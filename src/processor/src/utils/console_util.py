# Color and icon utility functions for enhanced display
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

    # Additional colors (non-bright variants) for unique role styling
    DARK_RED = "\033[31m"
    DARK_GREEN = "\033[32m"
    DARK_YELLOW = "\033[33m"
    DARK_BLUE = "\033[34m"
    DARK_MAGENTA = "\033[35m"
    DARK_CYAN = "\033[36m"

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


def get_role_style(name=None):
    """Get color, icon, and formatting for different roles and agents"""

    # Role-based styling
    # Agent-specific styling
    agent_styles = {
        "Chief Architect": (
            f"{ConsoleColors.BOLD}{ConsoleColors.MAGENTA}Chief Architect{ConsoleColors.RESET}",
            ConsoleColors.MAGENTA,
        ),
        "GKE Expert": (
            f"{ConsoleColors.BOLD}{ConsoleColors.GREEN}GKE EXPERT{ConsoleColors.RESET}",
            ConsoleColors.GREEN,
        ),
        "EKS Expert": (
            f"{ConsoleColors.BOLD}{ConsoleColors.YELLOW}EKS EXPERT{ConsoleColors.RESET}",
            ConsoleColors.YELLOW,
        ),
        "Azure Expert": (
            f"{ConsoleColors.BOLD}{ConsoleColors.CYAN}AZURE EXPERT{ConsoleColors.RESET}",
            ConsoleColors.CYAN,
        ),
        "YAML Expert": (
            f"{ConsoleColors.BOLD}{ConsoleColors.WHITE}YAML EXPERT{ConsoleColors.RESET}",
            ConsoleColors.WHITE,
        ),
        "OpenShift Expert": (
            f"{ConsoleColors.BOLD}{ConsoleColors.BLUE}OpenShift EXPERT{ConsoleColors.RESET}",
            ConsoleColors.BLUE,
        ),
        "AKS Expert": (
            f"{ConsoleColors.BOLD}{ConsoleColors.RED}AKS EXPERT{ConsoleColors.RESET}",
            ConsoleColors.RED,
        ),
        "Rancher Expert": (
            f"{ConsoleColors.BOLD}{ConsoleColors.DARK_MAGENTA}RANCHER EXPERT{ConsoleColors.RESET}",
            ConsoleColors.DARK_MAGENTA,
        ),
        "Tanzu Expert": (
            f"{ConsoleColors.BOLD}{ConsoleColors.DARK_GREEN}Tanzu EXPERT{ConsoleColors.RESET}",
            ConsoleColors.DARK_GREEN,
        ),
        "OnPremK8s Expert": (
            f"{ConsoleColors.BOLD}{ConsoleColors.DARK_YELLOW}ONPREMK8s EXPERT{ConsoleColors.RESET}",
            ConsoleColors.DARK_YELLOW,
        ),
        "Technical Writer": (
            f"{ConsoleColors.BOLD}{ConsoleColors.DARK_CYAN}TECHNICAL WRITER{ConsoleColors.RESET}",
            ConsoleColors.DARK_CYAN,
        ),
        "QA Engineer": (
            f"{ConsoleColors.BOLD}{ConsoleColors.DARK_BLUE}QA ENGINEER{ConsoleColors.RESET}",
            ConsoleColors.DARK_BLUE,
        ),
    }

    if name and name in agent_styles:
        return agent_styles[name]
    else:
        return (
            f"{ConsoleColors.BOLD}{ConsoleColors.WHITE}COORDINATOR{ConsoleColors.RESET}",
            ConsoleColors.WHITE,
        )


def format_agent_message(name, content, timestamp, max_content_length=400):
    """Format agent message with colors, icons and truncation"""
    role_display, content_color = get_role_style(name)

    if content is None:
        content_text = ""
    else:
        content_text = str(content)

    if isinstance(max_content_length, int) and max_content_length > 0:
        if len(content_text) > max_content_length:
            if max_content_length <= 1:
                content_text = "…"
            else:
                content_text = content_text[: max_content_length - 1] + "…"

    content_display = f"{content_color}{content_text}{ConsoleColors.RESET}"

    return f"{role_display}: {content_display}{f' ({timestamp})' if timestamp else ''}"
