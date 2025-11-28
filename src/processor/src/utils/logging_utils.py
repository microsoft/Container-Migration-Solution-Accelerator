"""
Unified logging utilities for migration system.

Consolidates functionality from:
- quiet_logging.py (third-party suppression)
- safe_logger.py (safe string formatting)
- error_logging.py (enhanced error analysis)

Provides consistent logging interface across the migration system.
"""

import logging
import os
import traceback
from typing import Any

from azure.core.exceptions import HttpResponseError
from semantic_kernel.exceptions import ServiceException


def configure_application_logging(debug_mode: bool = False, config=None):
    """
    Comprehensive logging configuration with third-party suppression.

    Replaces suppress_verbose_logging() from quiet_logging.py

    Args:
        debug_mode: If True, allows some debug logging. If False, suppresses all debug output.
        config: Configuration object with logging settings. If None, uses default settings.
    """
    # Set root logger level
    if debug_mode:
        logging.basicConfig(level=logging.DEBUG)
        print("🐛 Debug logging enabled")
    else:
        # Use configuration if available, otherwise default to INFO
        basic_level = logging.INFO
        if config and hasattr(config, 'app_logging_level'):
            basic_level = getattr(logging, config.app_logging_level.upper(), logging.INFO)
        logging.basicConfig(level=basic_level)

    # Comprehensive list of verbose loggers to suppress
    verbose_loggers = [
        # Azure SDK loggers
        "azure.core.pipeline.policies.http_logging_policy",
        "azure.storage.blob",
        "azure.storage.queue",
        "azure.core",
        "azure.identity",
        "azure.storage",
        "azure.core.pipeline",
        "azure.core.pipeline.policies",
        "azure.core.pipeline.transport",
        # OpenAI and HTTP client loggers
        "openai",
        "openai._client",
        "openai._base_client",
        "openai._utils",
        "openai.resources",
        "openai.lib",
        "httpx",
        "httpx._client",
        "httpcore",
        "httpcore.connection_pool",
        "httpcore.http11",
        "httpcore.http2",
        # Semantic Kernel loggers
        "semantic_kernel",
        "semantic_kernel.connectors",
        "semantic_kernel.connectors.ai",
        "semantic_kernel.connectors.ai.open_ai",
        "semantic_kernel.connectors.ai.open_ai.services",
        "semantic_kernel.connectors.ai.azure_ai_inference",
        "semantic_kernel.agents",
        "semantic_kernel.agents.runtime",
        "semantic_kernel.functions",
        # Other HTTP/network libraries
        "urllib3",
        "urllib3.connectionpool",
        "urllib3.util.retry",
        "requests",
        "requests.packages.urllib3",
        "msal",
        "msal.token_cache",
        # Additional verbose libraries
        "asyncio",
        "multipart",
        "charset_normalizer",
    ]

    # Configure Azure package logging levels from configuration only if packages are specified
    if config and hasattr(config, 'azure_logging_packages') and hasattr(config, 'azure_package_logging_level') and config.azure_logging_packages:
        # Use configuration-based approach
        azure_level = getattr(logging, config.azure_package_logging_level.upper(), logging.WARNING)
        package_list = [pkg.strip() for pkg in config.azure_logging_packages.split(',')]
        for logger_name in package_list:
            if logger_name:  # Skip empty strings
                logging.getLogger(logger_name).setLevel(azure_level)
    else:
        # Fallback to existing logic for backward compatibility
        # Set levels for all verbose loggers
        for logger_name in verbose_loggers:
            logger = logging.getLogger(logger_name)
            if debug_mode:
                # In debug mode, still reduce verbosity to INFO for most, WARNING for HTTP
                if any(
                    http_term in logger_name.lower()
                    for http_term in ["http", "client", "connection", "pipeline"]
                ):
                    logger.setLevel(logging.WARNING)
                else:
                    logger.setLevel(logging.INFO)
            else:
                # In production, suppress to WARNING for all
                logger.setLevel(logging.WARNING)

        # Special cases: These are ALWAYS set to WARNING due to extreme verbosity
        always_warning_loggers = [
            "azure.core.pipeline.policies.http_logging_policy",
            "httpx",
            "httpcore",
            "openai._client",
            "urllib3.connectionpool",
        ]

        for logger_name in always_warning_loggers:
            logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Set environment variables to suppress verbose output at the source
    os.environ.setdefault("HTTPX_LOG_LEVEL", "WARNING")
    os.environ.setdefault("AZURE_CORE_ENABLE_HTTP_LOGGER", "false")

    if debug_mode:
        print("🔇 Verbose logging suppressed (debug mode: some INFO logging allowed)")
    else:
        print("🔇 All verbose logging suppressed (production mode)")


def create_migration_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Create standardized logger for migration system.

    Replaces create_quiet_logger() from quiet_logging.py and
    create_safe_logger() from safe_logger.py

    Args:
        name: Logger name
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)

    return logger


def safe_log(logger: logging.Logger, level: str, message: str, **kwargs):
    """
    Safe logging with variable substitution that won't break on JSON/braces.

    Replaces SafeLogger template functionality from safe_logger.py

    Args:
        logger: Logger instance to use
        level: Log level ('info', 'error', 'warning', 'debug')
        message: Message template with {variable} placeholders
        **kwargs: Variables to substitute in message
    """
    try:
        # Pre-process kwargs to safely handle complex objects
        safe_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, dict | list):
                # Convert complex objects to string representation
                safe_kwargs[key] = str(value)
            elif isinstance(value, Exception):
                # Convert exceptions to safe string representation
                safe_kwargs[key] = str(value)
            else:
                safe_kwargs[key] = value

        # Use simple string format to avoid f-string issues with JSON/braces
        formatted_message = message.format(**safe_kwargs)

        # Log at appropriate level
        log_method = getattr(logger, level.lower())
        log_method(formatted_message)

    except Exception as e:
        # If formatting fails, log clear error without fallback confusion
        logger.error(
            f"CRITICAL: Log format failed - {e} | Message: {message} | Data: {kwargs}"
        )
        raise RuntimeError(f"Safe logger format failure: {e}") from e


def get_error_details(exception: Exception) -> dict[str, Any]:
    """
    Extract comprehensive error details from any exception.

    Simplified version of get_comprehensive_error_details() from error_logging.py

    Args:
        exception: The exception to analyze

    Returns:
        Dictionary containing detailed error information
    """
    details = {
        "exception_type": type(exception).__name__,
        "exception_module": type(exception).__module__,
        "exception_message": str(exception),
        "full_traceback": traceback.format_exc(),
        "exception_args": getattr(exception, "args", []),
        "exception_cause": str(exception.__cause__) if exception.__cause__ else None,
        "exception_context": str(exception.__context__) if exception.__context__ else None,
    }

    # Add specific details for Azure HTTP errors
    if isinstance(exception, HttpResponseError):
        details.update({
            "http_status_code": getattr(exception, "status_code", None),
            "http_reason": getattr(exception, "reason", None),
            "http_response": getattr(exception, "response", None),
            "http_model": getattr(exception, "model", None),
        })

    # Add specific details for Semantic Kernel Service exceptions
    if isinstance(exception, ServiceException):
        details.update({
            "service_error_code": getattr(exception, "error_code", None),
            "service_inner_exception": getattr(exception, "inner_exception", None),
        })

    # Add details for AzureChatCompletion specific errors
    if "AzureChatCompletion" in str(type(exception)):
        details.update({
            "azure_chat_completion_error": True,
            "model_deployment": getattr(exception, "model", None),
            "endpoint": getattr(exception, "endpoint", None),
        })

    return details


def log_error_with_context(
    logger: logging.Logger,
    exception: Exception,
    context: str = "Operation",
    **kwargs
):
    """
    Enhanced error logging with context and exception analysis.

    Simplified version of log_comprehensive_error() from error_logging.py

    Args:
        logger: Logger instance to use
        exception: The exception to log
        context: Context description for the error
        **kwargs: Additional context information
    """
    error_details = get_error_details(exception)

    # Add additional context
    if kwargs:
        error_details["additional_context"] = kwargs

    # Log comprehensive error information
    logger.error(
        "[FAILED] %s error details:\n"
        "Exception Type: %s\n"
        "Exception Module: %s\n"
        "Exception Message: %s\n"
        "Exception Args: %s\n"
        "Exception Cause: %s\n"
        "Exception Context: %s\n"
        "%s"
        "Full Traceback:\n%s",
        context,
        error_details["exception_type"],
        error_details["exception_module"],
        error_details["exception_message"],
        error_details["exception_args"],
        error_details["exception_cause"],
        error_details["exception_context"],
        _format_specific_error_details(error_details),
        error_details["full_traceback"],
    )

    return error_details


def _format_specific_error_details(error_details: dict[str, Any]) -> str:
    """Format specific error details for HTTP/Service/Azure errors."""
    specific_info = []

    if "http_status_code" in error_details:
        specific_info.append(f"HTTP Status Code: {error_details['http_status_code']}")
        specific_info.append(f"HTTP Reason: {error_details['http_reason']}")

    if "service_error_code" in error_details:
        specific_info.append(f"Service Error Code: {error_details['service_error_code']}")

    if error_details.get("azure_chat_completion_error"):
        specific_info.append("Azure ChatCompletion Error Detected")
        if error_details.get("model_deployment"):
            specific_info.append(f"Model Deployment: {error_details['model_deployment']}")
        if error_details.get("endpoint"):
            specific_info.append(f"Endpoint: {error_details['endpoint']}")

    return "\n".join(specific_info) + "\n" if specific_info else ""


# Common log message templates
class LogMessages:
    """Pre-defined message templates for common logging patterns."""

    ERROR_STEP_FAILED = "[FAILED] {step} failed: {error}"
    ERROR_STEP_ACTIVATION = "[FAILED] {step} step activation failed: {error}"
    ERROR_GROUP_CHAT = "[FAILED] Group chat {operation} failed: {error}"
    ERROR_EXTRACTION = "[FAILED] Failed to extract {type} results: {error}"
    ERROR_FALLBACK = "[FAILED] Fallback {operation} failed: {error}"
    ERROR_CONTEXT_CLEANUP = "[FAILED] Context cleanup failed: {error}"

    SUCCESS_COMPLETED = "[SUCCESS] {operation} completed: {details}"
    SUCCESS_STEP = "[SUCCESS] {step} step completed successfully"

    INFO_RESULT = "[INFO] {operation} result: {result}"
    INFO_PROCESSING = "[PROCESSING] Processing {item}..."
