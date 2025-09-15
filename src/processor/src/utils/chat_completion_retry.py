"""
Chat Completion Retry Utility for Azure OpenAI Service Resilience

This module provides robust retry logic for get_chat_message_content calls with:
- Exponential backoff with jitter
- Configurable retry parameters
- Comprehensive error handling
- Telemetry integration
- Context preservation across retries

Usage:
    from utils.chat_completion_retry import get_chat_message_content_with_retry, get_conservative_retry_config

    response = await get_chat_message_content_with_retry(
        service,
        chat_history,
        settings=PromptExecutionSettings(response_format=StringResult),
        config=get_conservative_retry_config()
    )
"""

import asyncio
from dataclasses import dataclass
import logging
import random
from typing import Any

from semantic_kernel.connectors.ai.chat_completion_client_base import (
    ChatCompletionClientBase,
)
from semantic_kernel.connectors.ai.prompt_execution_settings import (
    PromptExecutionSettings,
)
from semantic_kernel.contents import ChatHistory

# Import credential refresh utilities
from utils.credential_util import get_azure_credential

logger = logging.getLogger(__name__)


@dataclass
class ChatCompletionRetryConfig:
    """Configuration for chat completion retry logic."""

    max_retries: int = 3
    base_delay: float = 2.0  # Base delay in seconds
    max_delay: float = 30.0  # Maximum delay cap
    exponential_base: float = 2.0  # Exponential backoff multiplier
    timeout_seconds: float = 60.0  # Timeout per attempt
    jitter: bool = True  # Add randomization to prevent thundering herd
    retryable_errors: list[str] | None = None

    def __post_init__(self):
        """Set default retryable errors if not provided."""
        if self.retryable_errors is None:
            self.retryable_errors = [
                "APITimeoutError",
                "APIConnectionError",
                "RateLimitError",
                "InternalServerError",
                "ServiceUnavailableError",
                "BadGatewayError",
                "GatewayTimeoutError",
            ]


def get_conservative_retry_config() -> ChatCompletionRetryConfig:
    """Get conservative retry configuration."""
    return ChatCompletionRetryConfig(
        max_retries=3,
        base_delay=2.0,
        max_delay=30.0,
        exponential_base=2.0,
        timeout_seconds=60.0,
    )


def get_aggressive_retry_config() -> ChatCompletionRetryConfig:
    """Get aggressive retry configuration."""
    return ChatCompletionRetryConfig(
        max_retries=5,
        base_delay=1.0,
        max_delay=60.0,
        exponential_base=2.5,
        timeout_seconds=90.0,
    )


def get_orchestration_retry_config() -> ChatCompletionRetryConfig:
    """Get orchestration retry configuration."""
    return ChatCompletionRetryConfig(
        max_retries=5,
        base_delay=2.0,
        max_delay=30.0,
        exponential_base=2.0,
        timeout_seconds=60.0,
        retryable_errors=[
            "APITimeoutError",
            "APIConnectionError",
            "RateLimitError",
            "InternalServerError",
            "ServiceResponseException",  # This is key - the wrapper exception!
            "TimeoutError",
            "ConnectTimeout",
            "ReadTimeout",
            "AuthenticationError",  # Added for smart auth retry handling
        ],
    )


def _is_auth_error_retryable(exception: Exception) -> bool:
    """
    Determine if an AuthenticationError should be retried.

    Only retry token refresh timing issues, not actual permission problems.
    This prevents masking real permission issues while handling token timing.
    """
    error_msg = str(exception).lower()

    # NEVER retry true permission/configuration issues - fail fast
    permanent_failure_patterns = [
        "insufficient privileges",
        "access denied",
        "forbidden",
        "not authorized",
        "invalid subscription",
        "quota exceeded",
        "invalid client",
        "invalid secret",
    ]

    # Don't retry if it's clearly a configuration/permission issue
    if any(pattern in error_msg for pattern in permanent_failure_patterns):
        logger.warning(
            f"[AUTH] Permanent auth failure detected - no retry: {error_msg[:150]}..."
        )
        return False

    # DO retry ALL token-related and timing issues (including "permissiondenied" which is often token timing)
    retryable_auth_patterns = [
        "token",
        "authentication failed",
        "credential",
        "expired",
        "refresh",
        "temporary",
        "transient",
        "timeout",
        "permissiondenied",  # Often token timing, not true permission issue
        "lacks the required data action",  # Also often token state, not true permission
    ]

    is_retryable = any(pattern in error_msg for pattern in retryable_auth_patterns)

    if is_retryable:
        logger.info(
            f"[AUTH] Retryable auth error detected - will retry: {error_msg[:150]}..."
        )
    else:
        logger.warning(
            f"[AUTH] Non-retryable auth error - failing fast: {error_msg[:150]}..."
        )

    return is_retryable


async def _refresh_credentials_if_needed(service: ChatCompletionClientBase, exception: Exception) -> bool:
    """
    Attempt to refresh credentials if authentication error indicates token expiration.

    For Azure services using token providers, this forces a new token request.

    Returns:
        True if credential refresh was attempted, False otherwise
    """
    exception_name = type(exception).__name__

    # Only attempt refresh for authentication errors
    if exception_name != "AuthenticationError":
        return False

    error_msg = str(exception).lower()

    # Only refresh for token-related issues
    token_related_patterns = [
        "token",
        "expired",
        "invalid",
        "missing",
        "unauthorized"
    ]

    if not any(pattern in error_msg for pattern in token_related_patterns):
        return False

    try:
        logger.info("[AUTH] Attempting credential refresh for token expiration...")

        # For Azure OpenAI services using token providers, we need to trigger a token refresh
        # The token provider should automatically handle refresh, but sometimes needs a manual trigger

        # Check if service has ad_token_provider (Azure OpenAI with Entra ID)
        if hasattr(service, '_ad_token_provider') and service._ad_token_provider:
            logger.info("[AUTH] Found Azure AD token provider - triggering token refresh")

            # Force a new token request by calling the provider directly
            # This triggers the underlying credential to refresh its token
            try:
                # Import the Azure scopes for OpenAI
                azure_openai_scope = "https://cognitiveservices.azure.com/.default"

                # The token provider is typically a callable that takes a scope
                # Calling it will force the underlying credential to refresh if needed
                fresh_token = await service._ad_token_provider(azure_openai_scope)
                logger.info("[AUTH] Successfully triggered token refresh via AD token provider")
                return True

            except Exception as token_error:
                logger.warning(f"[AUTH] Token provider refresh failed: {token_error}")

        # Fallback: Try to get a fresh credential and see if we can update the service
        elif hasattr(service, '_credential'):
            credential = get_azure_credential()
            service._credential = credential
            logger.info("[AUTH] Service credential updated with fresh token")
            return True

        else:
            logger.warning("[AUTH] Service doesn't expose token provider or credential - refresh may not be effective")

        return False

    except Exception as refresh_error:
        logger.warning(f"[AUTH] Credential refresh failed: {refresh_error}")
        return False


def _is_retryable_error(
    exception: Exception, retryable_errors: list[str] | None
) -> bool:
    """Check if an exception is retryable based on configuration."""
    if not retryable_errors:
        return False

    exception_name = type(exception).__name__

    # SMART AUTHENTICATION ERROR HANDLING
    if exception_name == "AuthenticationError":
        return _is_auth_error_retryable(exception)

    # Check direct exception name match
    if exception_name in retryable_errors:
        return True

    # Check if it's wrapped in a ServiceResponseException
    if hasattr(exception, "__cause__") and exception.__cause__:
        cause_name = type(exception.__cause__).__name__
        if cause_name in retryable_errors:
            return True

    # Check exception message for specific patterns
    error_message = str(exception).lower()
    return any(
        error.lower() in error_message
        for error in [
            "timeout",
            "connection",
            "rate limit",
            "internal server",
            "service unavailable",
            "bad gateway",
            "gateway timeout",
        ]
    )


def _calculate_delay(attempt: int, config: ChatCompletionRetryConfig) -> float:
    """Calculate delay for the given attempt with exponential backoff and jitter."""
    # Exponential backoff: base_delay * (exponential_base ^ attempt)
    delay = config.base_delay * (config.exponential_base**attempt)

    # Apply maximum delay cap
    delay = min(delay, config.max_delay)

    # Add jitter to prevent thundering herd problems
    if config.jitter:
        # Add up to 25% random jitter
        jitter_range = delay * 0.25
        delay += random.uniform(-jitter_range, jitter_range)

    # Ensure delay is not negative
    return max(0.1, delay)


async def get_chat_message_content_with_retry(
    service: ChatCompletionClientBase,
    chat_history: ChatHistory,
    settings: PromptExecutionSettings,
    config: ChatCompletionRetryConfig | None = None,
    operation_name: str = "chat_completion",
) -> Any:
    """
    Execute get_chat_message_content with retry logic and exponential backoff.

    Args:
        service: The chat completion service
        chat_history: Chat history for the request
        settings: Prompt execution settings
        config: Retry configuration (defaults to conservative config if None)
        operation_name: Name for logging purposes

    Returns:
        Response from get_chat_message_content

    Raises:
        Exception: Final exception after all retries exhausted
    """
    # Use conservative config as default if none provided
    if config is None:
        config = get_conservative_retry_config()

    last_exception = None

    for attempt in range(config.max_retries + 1):  # +1 for initial attempt
        try:
            logger.info(
                f"[RETRY] {operation_name} attempt {attempt + 1}/{config.max_retries + 1}"
            )

            # Create timeout for this specific attempt
            response = await asyncio.wait_for(
                service.get_chat_message_content(chat_history, settings=settings),
                timeout=config.timeout_seconds,
            )

            if attempt > 0:
                logger.info(
                    f"[RETRY] {operation_name} succeeded on attempt {attempt + 1}"
                )

            return response

        except Exception as e:
            last_exception = e

            logger.warning(
                f"[RETRY] {operation_name} attempt {attempt + 1} failed: {type(e).__name__}: {str(e)}"
            )

            # If this is the last attempt, don't retry
            if attempt >= config.max_retries:
                logger.error(
                    f"[RETRY] {operation_name} failed after {config.max_retries + 1} attempts. "
                    f"Final error: {type(e).__name__}: {str(e)}"
                )
                break

            # Check if error is retryable
            if not _is_retryable_error(e, config.retryable_errors):
                logger.error(
                    f"[RETRY] {operation_name} failed with non-retryable error: {type(e).__name__}: {str(e)}"
                )
                break

            # For authentication errors, attempt credential refresh before retrying
            refresh_attempted = await _refresh_credentials_if_needed(service, e)
            if refresh_attempted:
                logger.info(f"[AUTH] Credential refresh attempted - retrying immediately")
                # Use shorter delay for credential refresh retries
                delay = min(1.0, _calculate_delay(attempt, config))
            else:
                # Calculate normal delay and wait before retry
                delay = _calculate_delay(attempt, config)

            logger.info(f"[RETRY] {operation_name} retrying in {delay:.2f} seconds...")

            await asyncio.sleep(delay)

    # All retries exhausted, raise the last exception
    if last_exception is None:
        raise RuntimeError("Chat completion failed with unknown error")
    raise last_exception


# Convenience functions for common scenarios
async def get_chat_message_content_conservative_retry(
    service: ChatCompletionClientBase,
    chat_history: ChatHistory,
    settings: PromptExecutionSettings,
    operation_name: str = "chat_completion",
) -> Any:
    """Get chat message content with conservative retry strategy."""
    return await get_chat_message_content_with_retry(
        service, chat_history, settings, get_conservative_retry_config(), operation_name
    )


async def get_chat_message_content_aggressive_retry(
    service: ChatCompletionClientBase,
    chat_history: ChatHistory,
    settings: PromptExecutionSettings,
    operation_name: str = "chat_completion",
) -> Any:
    """Get chat message content with aggressive retry strategy."""
    return await get_chat_message_content_with_retry(
        service, chat_history, settings, get_aggressive_retry_config(), operation_name
    )
