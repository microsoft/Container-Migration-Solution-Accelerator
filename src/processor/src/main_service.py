"""
Queue-Based Migration Service - Main entry point for the queue processing service.

This replaces the direct execution approach with a scalable queue-based service that can:
- Process multiple migration requests concurrently
- Handle failures with automatic retry logic
- Scale horizontally with multiple service instances
- Provide comprehensive monitoring and observability
"""

import asyncio
import logging
import os

from libs.base.ApplicationBase import ApplicationBase
from services.queue_service import (
    QueueMigrationService,
    QueueServiceConfig,
)

logger = logging.getLogger(__name__)


class QueueMigrationServiceApp(ApplicationBase):
    """
    Queue-based migration service application.

    Transforms the direct-execution migration engine into a scalable service that:
    - Processes migration requests from Azure Storage Queue
    - Handles concurrent processing with multiple workers
    - Implements retry logic with exponential backoff
    - Provides comprehensive error handling and monitoring
    """

    def __init__(self, config_override: dict | None = None, **kwargs):
        """Initialize the queue service application"""
        super().__init__(**kwargs)
        self.queue_service: QueueMigrationService | None = None
        self.config_override = config_override or {}

        # Configure logging based on debug_mode from constructor
        self._configure_logging()

    def _configure_logging(self):
        """Configure logging based on debug_mode setting"""
        # Import and use comprehensive logging suppression
        from utils.logging_utils import configure_application_logging

        # Apply comprehensive verbose logging suppression
        configure_application_logging(debug_mode=self.debug_mode)

        if self.debug_mode:
            print("🐛 Debug logging enabled - level set to DEBUG")
            logger.debug("🔇 Verbose third-party logging suppressed to reduce noise")

    async def initialize_service(self):
        """
        Initialize the queue migration service with configuration.
        """
        # Initialize the ApplicationBase (this sets up app_context with Cosmos DB config)
        await super().initialize_async()

        # Only log initialization if debug mode is explicitly enabled
        if self.debug_mode:
            logger.info("[DOCKER] Initializing Queue Migration Service...")

        # Build service configuration
        config = self._build_service_config(self.config_override)

        # Create queue migration service
        self.queue_service = QueueMigrationService(
            config=config,
            app_context=self.app_context,
            debug_mode=self.debug_mode,  # Use the debug_mode from constructor
        )

        logger.info("✅ Queue Migration Service initialized for Docker deployment")

    def _build_service_config(
        self, config_override: dict | None = None
    ) -> QueueServiceConfig:
        """Build service configuration from environment and overrides"""

        # Get configuration from environment variables (Docker-friendly)

        # Add protective checks for environment variables
        visibility_timeout = os.getenv("VISIBILITY_TIMEOUT_MINUTES", "5")
        max_retry_count = os.getenv("MAX_RETRY_COUNT", "0")
        poll_interval = os.getenv("POLL_INTERVAL_SECONDS", "5")
        message_timeout = os.getenv("MESSAGE_TIMEOUT_MINUTES", "25")

        # Debug print to see what we're getting (only if debug mode is enabled)
        if self.debug_mode:
            print("DEBUG - Environment variables:")
            print(
                f"  VISIBILITY_TIMEOUT_MINUTES: {visibility_timeout} (type: {type(visibility_timeout)})"
            )
            print(
                f"  MAX_RETRY_COUNT: {max_retry_count} (type: {type(max_retry_count)})"
            )
            print(
                f"  POLL_INTERVAL_SECONDS: {poll_interval} (type: {type(poll_interval)})"
            )
            print(
                f"  MESSAGE_TIMEOUT_MINUTES: {message_timeout} (type: {type(message_timeout)})"
            )

        config = QueueServiceConfig(
            use_entra_id=True,
            storage_account_name=self.app_context.configuration.storage_queue_account,  # type:ignore
            queue_name=self.app_context.configuration.storage_account_process_queue,  # type:ignore
            dead_letter_queue_name=f"{self.app_context.configuration.storage_account_process_queue}-dead-letter-queue",
            visibility_timeout_minutes=int(visibility_timeout)
            if isinstance(visibility_timeout, str)
            else visibility_timeout,
            max_retry_count=int(max_retry_count)
            if isinstance(max_retry_count, str)
            else max_retry_count,
            poll_interval_seconds=int(poll_interval)
            if isinstance(poll_interval, str)
            else poll_interval,
            message_timeout_minutes=int(message_timeout)
            if isinstance(message_timeout, str)
            else message_timeout,
        )

        # Apply any overrides
        if config_override:
            for key, value in config_override.items():
                if hasattr(config, key):
                    setattr(config, key, value)

        return config

    async def start_service(self):
        """Start the queue processing service"""
        if not self.queue_service:
            raise RuntimeError(
                "Service not initialized. Call initialize_service() first."
            )

        logger.info("🐳 Starting Queue-based Migration Service...")

        try:
            # Start the service (this will run until stopped)
            await self.queue_service.start_service()
        except KeyboardInterrupt:
            logger.info("🛑 Service interrupted by user (SIGTERM/SIGINT)")
        except Exception as e:
            logger.error(f"❌ Service error: {e}")
        finally:
            await self.shutdown_service()
            logger.info("🐳 Service stopped")

    async def shutdown_service(self):
        """Gracefully shutdown the service"""
        if self.queue_service:
            logger.info("Shutting down Queue Migration Service...")
            await self.queue_service.stop_service()
            self.queue_service = None

        logger.info("Service shutdown complete")

    async def force_stop_service(self):
        """Force immediate shutdown of the service"""
        if self.queue_service:
            logger.warning("🚨 Force stopping Queue Migration Service...")
            await self.queue_service.force_stop()
            self.queue_service = None

        logger.info("Service force stopped")

    def is_service_running(self) -> bool:
        """Check if the service is currently running"""
        return self.queue_service is not None and self.queue_service.is_running

    def get_service_status(self) -> dict:
        """Get current service status"""
        if not self.queue_service:
            return {
                "status": "not_initialized",
                "running": False,
                "docker_health": "unhealthy",
                "timestamp": asyncio.get_event_loop().time()
                if hasattr(asyncio, "get_event_loop")
                else None,
            }

        status = self.queue_service.get_service_status()
        status["running"] = self.is_service_running()
        status["docker_health"] = (
            "healthy" if self.is_service_running() else "unhealthy"
        )
        return status

    async def run(self):
        """Run the migration service"""
        # Initializing Queue Service
        await self.initialize_service()
        # Starting the Queue Service
        await self.start_service()

    # Message utilities for testing and queue management

    # Main execution functions


async def run_queue_service(
    config_override: dict | None = None, debug_mode: bool = False
):
    """
    Run the queue-based migration service with Docker auto-restart support.

    Args:
        config_override: Optional configuration overrides
        debug_mode: Enable debug logging and detailed telemetry
    """
    # Create service application
    app = QueueMigrationServiceApp(
        config_override=config_override,
        debug_mode=debug_mode,
        env_file_path=os.path.join(os.path.dirname(__file__), ".env"),
    )

    try:
        # Initialize and start service
        logger.info("🐳 Docker container starting queue service...")
        await app.run()
    except KeyboardInterrupt:
        logger.info("🐳 Docker container received shutdown signal")
        # Properly stop the service before exiting
        try:
            if app.queue_service:
                await app.queue_service.stop_service()
            logger.info("Service shutdown complete")
        except Exception as cleanup_error:
            logger.warning(f"Error during cleanup: {cleanup_error}")
        logger.info("🐳 Service stopped")
        # Exit gracefully without raising the KeyboardInterrupt
    except Exception as e:
        logger.error(f"❌ Failed to run queue service: {e}")
        # Attempt cleanup even on errors
        try:
            if app.queue_service:
                await app.queue_service.stop_service()
        except Exception:
            pass  # Ignore cleanup errors during exception handling
        # Exit with error code - Docker will restart if configured
        raise


# Entry point
if __name__ == "__main__":
    # Allow debug mode to be controlled by environment variable
    debug_mode = True
    asyncio.run(run_queue_service(debug_mode=debug_mode))
