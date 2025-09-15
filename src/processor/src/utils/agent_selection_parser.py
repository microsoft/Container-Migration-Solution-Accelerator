"""
Agent Selection Parser - Robust StringResult parsing for agent selection responses.

Handles both JSON and plain text responses from AI models, providing graceful
fallback for models that don't strictly follow JSON formatting requirements.
"""

import json
import logging
import re
import unicodedata

from pydantic import ValidationError
from semantic_kernel.agents.orchestration.group_chat import StringResult

logger = logging.getLogger(__name__)


def parse_agent_selection_safely(
    content: str, step_name: str, valid_agents: list[str] | None = None
) -> StringResult:
    """
    Parse agent selection response with robust fallback handling.

    Handles various AI response formats:
    - Proper JSON: {"result": "QA_Engineer", "reason": "Selected for expertise"}
    - Plain text: "QA_Engineer"
    - Quoted text: '"QA_Engineer"'
    - With prefixes: "Select QA_Engineer"

    Args:
        content: Raw AI response content
        step_name: Step context (YAML, Analysis, Design, Documentation)
        valid_agents: Optional list to validate agent names against

    Returns:
        StringResult with agent name and contextual reason

    Raises:
        RuntimeError: If content is empty or agent cannot be determined
    """
    if not content or not content.strip():
        raise RuntimeError("Empty response content received for agent selection")

    # Step 1: Try JSON parsing first (preferred format)
    try:
        result = StringResult.model_validate_json(content)
        logger.debug(f"[AGENT_SELECTION] JSON parsing successful for {step_name} step")
        return result
    except (json.JSONDecodeError, ValidationError) as e:
        logger.info(
            f"[AGENT_SELECTION] JSON parsing failed for {step_name}, using fallback: {e}"
        )

    # Step 2: Fallback to plain text parsing
    clean_agent = _sanitize_agent_name(content)

    if not clean_agent:
        raise RuntimeError(f"Could not extract agent name from content: '{content}'")

    # Step 3: Validate against known agents if provided
    if valid_agents and clean_agent not in valid_agents:
        # Try fuzzy matching
        clean_agent = _find_closest_agent(clean_agent, valid_agents)
    
    # Step 3.5: Final validation - ensure we never return invalid agent names
    if valid_agents and clean_agent not in valid_agents:
        logger.error(
            f"[AGENT_SELECTION] Invalid agent '{clean_agent}' after all processing. Content: '{content}'"
        )
        logger.error(f"[AGENT_SELECTION] Valid agents: {valid_agents}")
        # Force fallback to first valid agent
        clean_agent = valid_agents[0]
        logger.warning(f"[AGENT_SELECTION] Force fallback to '{clean_agent}'")

    # Step 4: Generate contextual reason
    reason = _generate_selection_reason(clean_agent, step_name)

    result = StringResult(result=clean_agent, reason=reason)
    logger.info(
        f"[AGENT_SELECTION] Fallback parsing successful: {clean_agent} for {step_name}"
    )
    return result


def _sanitize_agent_name(content: str) -> str:
    """Clean up agent name from various AI response formats."""
    # Remove quotes, whitespace, common prefixes
    clean = content.strip().strip('"').strip("'")

    # Remove invisible Unicode characters that can cause matching issues
    # Normalize Unicode and remove zero-width characters
    clean = unicodedata.normalize("NFKC", clean)
    clean = re.sub(r"[\u200B-\u200D\uFEFF\u2060]", "", clean)  # Remove invisible chars

    # Remove common prefixes that AI might add
    prefixes = [
        "Select ",
        "Agent: ",
        "Next: ",
        "Choose ",
        "I select ",
        "Selected ",
        "I choose ",
    ]
    for prefix in prefixes:
        if clean.startswith(prefix):
            clean = clean[len(prefix) :].strip()

    # Handle multiline responses - take first line
    clean = clean.split("\n")[0].strip()

    # CRITICAL: Handle termination words that should never be agent names
    termination_words = ["Success", "Complete", "Terminate", "Finished", "Done", "End", "Yes", "No", "True", "False"]
    if clean in termination_words:
        logger.warning(
            f"[AGENT_SELECTION] Detected termination word '{clean}' - this indicates a prompt issue"
        )
        logger.warning(f"[AGENT_SELECTION] Original content: '{content}'")
        return ""  # Return empty to trigger fallback logic

    # Final cleanup - keep only word characters and underscores for agent names
    clean = re.sub(r"[^\w_]", "", clean)

    return clean


def _find_closest_agent(agent_name: str, valid_agents: list[str]) -> str:
    """Find closest matching agent name using fuzzy matching."""
    agent_lower = agent_name.lower()

    # Exact match (case insensitive)
    for valid_agent in valid_agents:
        if agent_lower == valid_agent.lower():
            return valid_agent

    # Partial match - agent name contains valid agent or vice versa
    for valid_agent in valid_agents:
        if agent_lower in valid_agent.lower() or valid_agent.lower() in agent_lower:
            logger.info(
                f"[AGENT_SELECTION] Fuzzy match: '{agent_name}' -> '{valid_agent}'"
            )
            return valid_agent

    # Enhanced fallback - use first valid agent
    fallback_agent = valid_agents[0] if valid_agents else agent_name

    logger.warning(
        f"[AGENT_SELECTION] No close match for '{agent_name}', using fallback '{fallback_agent}'"
    )
    logger.warning(
        "[AGENT_SELECTION] This may indicate a prompt formatting issue - check selection prompts"
    )

    return fallback_agent


def _generate_selection_reason(agent_name: str, step_name: str) -> str:
    """Generate contextual reason for agent selection based on step."""
    step_expertise = {
        "YAML": "YAML conversion and Kubernetes manifest transformation",
        "Analysis": "platform analysis and complexity assessment",
        "Design": "Azure architecture design and service recommendations",
        "Documentation": "technical documentation and migration guides",
    }

    expertise = step_expertise.get(step_name, f"{step_name} step processing")
    return f"Selected {agent_name} for {expertise} expertise"
