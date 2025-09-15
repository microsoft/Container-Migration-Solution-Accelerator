"""
Retry Manager - Handles retry logic with exponential backoff for queue message processing.

Features:
- Exponential backoff with jitter
- Configurable max retries and delay limits
- Error classification for retry decisions
- Comprehensive retry metrics and logging
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
import logging
import random
import time

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Classification of errors for retry decisions"""

    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"
    CRITICAL = "critical"
    TIMEOUT = "timeout"
    RESOURCE_EXHAUSTED = "resource_exhausted"


class RetryableError(Exception):
    """Exception that should be retried"""

    def __init__(self, message: str, error_type: ErrorType = ErrorType.RETRYABLE):
        super().__init__(message)
        self.error_type = error_type


@dataclass
class RetryMetrics:
    """Metrics for retry operations"""

    total_attempts: int = 0
    successful_retries: int = 0
    failed_retries: int = 0
    max_retries_exceeded: int = 0
    total_retry_time: float = 0.0
    average_retry_delay: float = 0.0


class RetryManager:
    """
    Manages retry logic with exponential backoff and jitter.

    Features:
    - Exponential backoff: delay = base_delay * (2 ^ attempt_number)
    - Jitter: Random variation to prevent thundering herd
    - Configurable limits: max_retries, base_delay, max_delay
    - Error classification: Different retry strategies based on error type
    """

    def __init__(
        self,
        max_retries: int = 5,
        base_delay_seconds: float = 30.0,
        max_delay_seconds: float = 300.0,
        jitter_factor: float = 0.1,
        backoff_multiplier: float = 2.0,
    ):
        self.max_retries = max_retries
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.jitter_factor = jitter_factor
        self.backoff_multiplier = backoff_multiplier

        # Metrics tracking
        self.metrics = RetryMetrics()

        logger.info(
            f"Retry Manager initialized - Max retries: {max_retries}, "
            f"Base delay: {base_delay_seconds}s, Max delay: {max_delay_seconds}s"
        )

    def calculate_delay(self, attempt_number: int) -> int:
        """
        Calculate retry delay with exponential backoff and jitter.

        Args:
            attempt_number: Current attempt number (0-based)

        Returns:
            Delay in seconds (integer for Azure Queue visibility timeout)
        """
        if attempt_number >= self.max_retries:
            return 0

        # Calculate exponential backoff: base_delay * (multiplier ^ attempt)
        exponential_delay = self.base_delay_seconds * (
            self.backoff_multiplier**attempt_number
        )

        # Apply maximum delay limit
        delay = min(exponential_delay, self.max_delay_seconds)

        # Add jitter to prevent thundering herd problem
        jitter_range = delay * self.jitter_factor
        jitter = random.uniform(-jitter_range, jitter_range)
        final_delay = max(1, delay + jitter)  # Ensure minimum 1 second

        return int(final_delay)

    def should_retry(
        self, attempt_number: int, error: Exception = None, error_type: ErrorType = None
    ) -> bool:
        """
        Determine if an operation should be retried based on attempt count and error type.

        Args:
            attempt_number: Current attempt number (0-based)
            error: The exception that occurred (optional)
            error_type: Classification of the error (optional)

        Returns:
            True if should retry, False otherwise
        """
        # Check max retries limit
        if attempt_number >= self.max_retries:
            self.metrics.max_retries_exceeded += 1
            return False

        # Determine error type from exception if not provided
        if error and not error_type:
            error_type = self._classify_error(error)

        # Make retry decision based on error type
        if error_type == ErrorType.NON_RETRYABLE:
            logger.info(f"Non-retryable error, skipping retry: {error}")
            return False
        elif error_type == ErrorType.CRITICAL:
            logger.error(f"[ALERT] Critical error, skipping retry: {error}")
            return False
        else:
            # RETRYABLE, TIMEOUT, RESOURCE_EXHAUSTED are retryable
            return True

    def _classify_error(self, error: Exception) -> ErrorType:
        """
        Classify error to determine retry strategy.

        Args:
            error: The exception to classify

        Returns:
            ErrorType classification
        """
        error_message = str(error).lower()
        error_type_name = type(error).__name__.lower()

        # Critical migration errors (from your existing code)
        if (
            hasattr(error, "is_critical_migration_error")
            and error.is_critical_migration_error
        ):
            return ErrorType.CRITICAL

        # Timeout errors
        if "timeout" in error_message or "timeouterror" in error_type_name:
            return ErrorType.TIMEOUT

        # Resource exhaustion
        if any(
            keyword in error_message
            for keyword in [
                "resource exhausted",
                "quota exceeded",
                "rate limit",
                "throttled",
            ]
        ):
            return ErrorType.RESOURCE_EXHAUSTED

        # Non-retryable errors
        if any(
            keyword in error_message
            for keyword in [
                "invalid",
                "malformed",
                "bad request",
                "unauthorized",
                "forbidden",
                "not found",
                "conflict",
                "unprocessable entity",
            ]
        ):
            return ErrorType.NON_RETRYABLE

        # Network and service errors (usually retryable)
        if any(
            keyword in error_message
            for keyword in [
                "connection",
                "network",
                "service unavailable",
                "internal server error",
                "bad gateway",
                "gateway timeout",
                "temporarily unavailable",
            ]
        ):
            return ErrorType.RETRYABLE

        # Default to retryable for unknown errors
        return ErrorType.RETRYABLE

    async def retry_with_backoff(
        self, operation, operation_name: str = "operation", *args, **kwargs
    ):
        """
        Execute an operation with retry logic and exponential backoff.

        Args:
            operation: Async function to execute
            operation_name: Name for logging purposes
            *args, **kwargs: Arguments to pass to operation

        Returns:
            Result of the operation

        Raises:
            Exception: The last exception if all retries are exhausted
        """
        last_exception = None
        start_time = time.time()

        for attempt in range(self.max_retries + 1):  # +1 for initial attempt
            try:
                self.metrics.total_attempts += 1

                if attempt > 0:
                    logger.info(
                        f"Retrying {operation_name} (attempt {attempt + 1}/{self.max_retries + 1})"
                    )

                # Execute the operation
                result = await operation(*args, **kwargs)

                if attempt > 0:
                    self.metrics.successful_retries += 1
                    elapsed_time = time.time() - start_time
                    logger.info(
                        f"{operation_name} succeeded after {attempt} retries "
                        f"in {elapsed_time:.2f}s"
                    )

                return result

            except Exception as e:
                last_exception = e

                # Check if we should retry
                if not self.should_retry(attempt, e):
                    break

                # Don't sleep after the last attempt
                if attempt < self.max_retries:
                    delay = self.calculate_delay(attempt)
                    logger.warning(
                        f"WARNING: {operation_name} failed (attempt {attempt + 1}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)

                    # Update metrics
                    self.metrics.total_retry_time += delay
                else:
                    self.metrics.failed_retries += 1

        # All retries exhausted
        total_elapsed = time.time() - start_time
        logger.error(
            f"{operation_name} failed after {self.max_retries + 1} attempts "
            f"in {total_elapsed:.2f}s. Last error: {last_exception}"
        )

        raise last_exception

    def get_metrics(self) -> RetryMetrics:
        """Get current retry metrics"""
        metrics = self.metrics

        # Calculate average retry delay
        if metrics.total_attempts > 0:
            metrics.average_retry_delay = metrics.total_retry_time / max(
                1, metrics.total_attempts - metrics.successful_retries
            )

        return metrics

    def reset_metrics(self):
        """Reset retry metrics"""
        self.metrics = RetryMetrics()
        logger.info("Retry metrics reset")

    def get_status(self) -> dict:
        """Get retry manager status and configuration"""
        metrics = self.get_metrics()

        return {
            "configuration": {
                "max_retries": self.max_retries,
                "base_delay_seconds": self.base_delay_seconds,
                "max_delay_seconds": self.max_delay_seconds,
                "jitter_factor": self.jitter_factor,
                "backoff_multiplier": self.backoff_multiplier,
            },
            "metrics": {
                "total_attempts": metrics.total_attempts,
                "successful_retries": metrics.successful_retries,
                "failed_retries": metrics.failed_retries,
                "max_retries_exceeded": metrics.max_retries_exceeded,
                "total_retry_time": metrics.total_retry_time,
                "average_retry_delay": metrics.average_retry_delay,
            },
        }


# Utility functions for common retry patterns


async def retry_azure_operation(
    operation, retry_manager: RetryManager, operation_name: str = "Azure operation"
):
    """Retry an Azure operation with appropriate error handling"""
    return await retry_manager.retry_with_backoff(
        operation, operation_name=operation_name
    )


async def retry_database_operation(
    operation, retry_manager: RetryManager, operation_name: str = "Database operation"
):
    """Retry a database operation with appropriate error handling"""
    return await retry_manager.retry_with_backoff(
        operation, operation_name=operation_name
    )
