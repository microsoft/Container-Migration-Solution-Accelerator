"""
Error Classification Utility

Provides error classification functionality for retry decision making
following enterprise patterns without requiring service instantiation.
"""

import asyncio
from enum import Enum
import logging
import os

logger = logging.getLogger(__name__)

# Configuration flag for retry behavior
# Set ALLOW_RETRIES=false to disable all retries (useful for debugging)
# Set ALLOW_RETRIES=true to enable normal retry logic
ALLOW_RETRIES = os.getenv("ALLOW_RETRIES", "false").lower() == "true"


class ErrorClassification(Enum):
    """Error classification for retry decision making"""

    RETRYABLE = "retryable"  # Temporary failures (network, timeout, resource)
    NON_RETRYABLE = "non_retryable"  # Critical errors (config, auth, validation)
    POISON_MESSAGE = "poison_message"  # Malformed input requiring dead letter handling
    IGNORABLE = "ignorable"  # Non-critical service errors that shouldn't block process


def classify_error(error: Exception) -> ErrorClassification:
    """
    Classify errors for retry decision making following enterprise patterns

    Args:
        error: Exception that occurred during processing

    Returns:
        ErrorClassification indicating retry strategy
    """
    # ENHANCED: AzureChatCompletion service errors - IGNORABLE (non-critical service issues)

    # Get error details for string matching
    error_str = str(error).lower()
    error_type = type(error).__name__

    if (
        "azurechatcompletion" in error_str
        or "azure_chat_completion" in error_str
        or "service failed to comp" in error_str  # The truncated error we're seeing
        or (
            "semantic_kernel.connectors.ai.open_ai.services" in error_str
            and "azurechatcompletion" in error_str
        )
    ):
        logger.info(
            f"[IGNORABLE] AzureChatCompletion service error detected (non-critical): {error_type}: {error_str[:200]}..."
        )
        return ErrorClassification.IGNORABLE

    # TEMPORARY: Disable all retries for debugging if ALLOW_RETRIES=false
    if not ALLOW_RETRIES:
        logger.info(
            f"[RETRIES_DISABLED] All errors classified as NON_RETRYABLE (ALLOW_RETRIES=false): {type(error).__name__}: {str(error)[:100]}..."
        )
        return ErrorClassification.NON_RETRYABLE
    # Check for explicit error classification
    if hasattr(error, "error_classification"):
        # Use dynamic access since this is a custom attribute that may not exist
        return getattr(error, "error_classification", ErrorClassification.RETRYABLE)

    # Critical migration errors - do not retry
    if hasattr(error, "is_critical_migration_error"):
        is_critical = getattr(error, "is_critical_migration_error", False)
        if is_critical:
            return ErrorClassification.NON_RETRYABLE

    # Network and timeout errors - typically retryable
    if isinstance(error, asyncio.TimeoutError | ConnectionError | OSError):
        return ErrorClassification.RETRYABLE

    # ENHANCED: Hard termination scenarios - RETRYABLE (infrastructure failures)
    if (
        "hard_terminated" in error_str
        or "hard termination" in error_str
        or "connection reset" in error_str
        or "connection refused" in error_str
        or "network unreachable" in error_str
        or "dns resolution failed" in error_str
        or "socket timeout" in error_str
    ):
        logger.info(
            f"[RETRYABLE] Hard termination/infrastructure error detected: {error_type}: {error_str[:200]}..."
        )
        return ErrorClassification.RETRYABLE

    # ENHANCED: ChatCompletion timeout and service errors - RETRYABLE for infrastructure, IGNORABLE for service issues
    if (
        "timeout" in error_str
        or "timed out" in error_str
        or "request timeout" in error_str
        or "connection timeout" in error_str
        or "read timeout" in error_str
        or "504" in error_str  # Gateway timeout
        or "502" in error_str  # Bad gateway (temporary)
        or "503" in error_str  # Service unavailable (temporary)
    ):
        logger.info(
            f"[RETRYABLE] Timeout/gateway error detected: {error_type}: {error_str[:200]}..."
        )
        return ErrorClassification.RETRYABLE

    # Azure Storage specific errors
    if "authorizationfailure" in error_str:
        # Check if it's a network access issue (retryable after config fix)
        if "public network access" in error_str or "firewall" in error_str:
            return ErrorClassification.RETRYABLE
        # Otherwise it's likely RBAC permissions (non-retryable without admin intervention)
        return ErrorClassification.NON_RETRYABLE

    # Authentication and authorization errors - do not retry
    if "auth" in error_str or "permission" in error_str or "credential" in error_str:
        return ErrorClassification.NON_RETRYABLE

    # Configuration and validation errors - do not retry
    if isinstance(error, ValueError | TypeError | AttributeError):
        return ErrorClassification.NON_RETRYABLE

    # ENHANCED: Agent prompt and termination structure errors - NON_RETRYABLE (configuration issues)
    if (
        "agents failed to provide required termination structure" in error_str
        or "agent prompt compliance" in error_str
        or "json format requirements" in error_str
        or "termination structure" in error_str
        or "agents must provide:" in error_str
    ):
        logger.info(
            f"[NON_RETRYABLE] Agent prompt/configuration error detected: {error_type}: {error_str[:200]}..."
        )
        return ErrorClassification.NON_RETRYABLE

    # ENHANCED: Rate limiting and temporary service errors - RETRYABLE
    if (
        "rate limit" in error_str
        or "too many requests" in error_str
        or "429" in error_str  # Too many requests
        or "throttle" in error_str
        or "quota" in error_str
        or "service unavailable" in error_str
    ):
        logger.info(
            f"[RETRYABLE] Rate limit/service error detected: {error_type}: {error_str[:200]}..."
        )
        return ErrorClassification.RETRYABLE

    # Default to retryable for unknown errors
    logger.debug(
        f"[RETRYABLE] Unknown error defaulting to retryable: {error_type}: {error_str[:200]}..."
    )
    return ErrorClassification.RETRYABLE
