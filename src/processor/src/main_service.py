# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

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

from libs.agent_framework.agent_framework_helper import AgentFrameworkHelper
from libs.agent_framework.mem0_async_memory import Mem0AsyncMemoryManager
from libs.agent_framework.middlewares import (
    DebuggingMiddleware,
    InputObserverMiddleware,
    LoggingFunctionMiddleware,
)
from libs.base.application_base import ApplicationBase
from services.control_api import ControlApiConfig, ControlApiServer
from services.process_control import ProcessControlManager
from services.queue_service import (
    QueueMigrationService,
    QueueServiceConfig,
)
from steps.migration_processor import MigrationProcessor
from utils.agent_telemetry import TelemetryManager
from utils.logging_utils import configure_application_logging

logger = logging.getLogger(__name__)


class QueueMigrationServiceApp(ApplicationBase):
    """
    Queue-based migration service application.

    Transforms the direct-execution migration engine into a scalable service that:
    - Processes migration requests from Azure Storage Queue
    - Handles concurrent processing with multiple workers
    - Implements retry logic with exponential backoff
    - Provides comprehensive error handling and monitoring

    Operationally, this class:
    - bootstraps the application context (config + DI container)
    - registers the services required by queue processing
    - builds runtime configuration from environment variables
    - starts/stops the queue worker and (optionally) the control API

    The entrypoint is `run_queue_service()` which constructs this app and runs it
    until stopped (SIGINT/SIGTERM in containers typically surface as KeyboardInterrupt).
    """

    def __init__(self, config_override: dict | None = None, debug_mode: bool = False):
        """Initialize the queue service application.

        Args:
            config_override: Optional configuration values to override environment defaults.
            debug_mode: Enables verbose debug logging and extra diagnostics.

        Runtime notes:
            - Loads environment configuration from the local `.env` next to this file.
            - Calls `initialize()` immediately, so the DI container is ready before
              the service loop begins.
        """
        super().__init__(env_file_path=os.path.join(os.path.dirname(__file__), ".env"))
        self.queue_service: QueueMigrationService | None = None
        self.control_api: ControlApiServer | None = None
        self.config_override = config_override or {}
        self.debug_mode = debug_mode

        # Configure logging based on debug_mode from constructor
        self._configure_logging()
        self.initialize()

    def _configure_logging(self):
        """Configure application logging for the current debug mode.

        This applies the repository's logging policy (including suppression of
        overly noisy third-party logs). When `debug_mode` is enabled, the service
        emits additional debug diagnostics to help trace queue processing.
        """

        # Apply comprehensive verbose logging suppression
        configure_application_logging(debug_mode=self.debug_mode)

        if self.debug_mode:
            print("🐛 Debug logging enabled - level set to DEBUG")
            logger.debug("🔇 Verbose third-party logging suppressed to reduce noise")

    def initialize(self):
        """Initialize the application and register services.

        This is the main bootstrap hook that prepares the runtime to start work.
        It populates the application context and registers all required services
        (agent framework helpers, telemetry, process control, and the migration
        processor).
        """
        print(
            "Application initialized with configuration:",
            self.application_context.configuration,
        )
        self.register_services()

    def register_services(self):
        """Register application services into the dependency injection container.

        This is the key wiring point for runtime behavior.

        The main registrations are:
        - `AgentFrameworkHelper` and middleware singletons (agent/run instrumentation)
        - `TelemetryManager` (async singleton)
        - `ProcessControlManager` (async singleton)
        - `MigrationProcessor` (transient per message)
        """

        # Additional initialization logic can be added here
        # -------------------------------------------------------------------------
        # Initialize AgentFrameworkHelper and add it to the application context
        # -------------------------------------------------------------------------
        self.application_context.add_singleton(
            AgentFrameworkHelper, AgentFrameworkHelper()
        )
        # Initialize AgentFrameworkHelper with LLM settings from application context
        self.application_context.get_service(AgentFrameworkHelper).initialize(
            self.application_context.llm_settings
        )

        # -------------------------------------------------------------------------
        # Initialize middlewares - All Middlewares below are registered as a singleton
        # -------------------------------------------------------------------------
        # InputObserverMiddleware(Agent Level)
        # LoggingFunctionMiddleware(Agent Level)
        # DebuggingMiddleware(Run Level)
        (
            # Register DebuggingMiddleware as a singleton
            self.application_context.add_singleton(
                DebuggingMiddleware, DebuggingMiddleware
            )
            # Register LoggingFunctionMiddleware as a singleton
            .add_singleton(LoggingFunctionMiddleware, LoggingFunctionMiddleware)
            .add_singleton(InputObserverMiddleware, InputObserverMiddleware)
            .add_singleton(Mem0AsyncMemoryManager, Mem0AsyncMemoryManager)
            .add_async_singleton(
                TelemetryManager, lambda: TelemetryManager(self.application_context)
            )
            .add_async_singleton(
                ProcessControlManager,
                lambda: ProcessControlManager(self.application_context),
            )
            .add_transient(
                MigrationProcessor,
                lambda: MigrationProcessor(app_context=self.application_context),
            )
        )

        # Optional: Cosmos checkpoint storage. This dependency can be version-sensitive
        # (agent_framework exports have changed across versions). If it's unavailable,
        # we skip registration so the app can still run.
        try:
            from libs.agent_framework.cosmos_checkpoint_storage import (
                CosmosCheckpointStorage,
                CosmosWorkflowCheckpointRepository,
            )

            self.application_context.add_singleton(
                CosmosCheckpointStorage,
                lambda: CosmosCheckpointStorage(
                    CosmosWorkflowCheckpointRepository(
                        account_url="https://[your cosmosdb].documents.azure.com:443/",
                        database_name="checkpoints",
                        container_name="workflow_checkpoints",
                    )
                ),
            )
        except Exception as e:
            # Keep it as a print to match the current style of this entrypoint.
            print(
                "[WARN] Cosmos checkpoint storage disabled due to import/config error:",
                e,
            )
        # Only log initialization if debug mode is explicitly enabled
        if self.debug_mode:
            logger.info("[DOCKER] Initializing Queue Migration Service...")

        # Build service configuration
        config = self._build_service_config(self.config_override)

        # Create queue migration service
        self.queue_service = QueueMigrationService(
            config=config,
            app_context=self.application_context,
            debug_mode=self.debug_mode,  # Use the debug_mode from constructor
        )

        # Control API is built/started from an async context in start_service().
        self.control_api = None

        logger.info("Queue Migration Service initialized for Docker deployment")

    async def _build_control_api(self) -> ControlApiServer | None:
        """Build the optional control API server from environment configuration.

        Operational behavior:
            - If disabled, the service runs without an HTTP control surface.
            - If enabled, the control API is started before the queue loop.

        Controlled by these environment variables:
        - `CONTROL_API_ENABLED` (default: enabled)
        - `CONTROL_API_TOKEN` (optional bearer token)
        - `CONTROL_API_HOST` (default: 0.0.0.0)
        - `CONTROL_API_PORT` (default: 8080)

        Returns a configured `ControlApiServer` instance, or `None` if disabled.
        """
        enabled = os.getenv("CONTROL_API_ENABLED", "1").strip().lower() not in {
            "0",
            "false",
            "no",
        }
        if not enabled:
            return None

        token = (os.getenv("CONTROL_API_TOKEN", "") or "").strip()

        # Internal-only API: bind to all interfaces by default so other apps
        # within the same environment/VNet can reach it. Deployment-time ingress
        # decides whether this is externally reachable.
        host = (os.getenv("CONTROL_API_HOST", "") or "").strip() or "0.0.0.0"

        try:
            port = int(os.getenv("CONTROL_API_PORT", "8080"))
        except Exception:
            port = 8080

        try:
            control: ProcessControlManager = await self.app_context.get_service_async(
                ProcessControlManager
            )
        except Exception:
            control = ProcessControlManager(self.application_context)

        return ControlApiServer(
            control=control,
            config=ControlApiConfig(
                enabled=True, host=host, port=port, bearer_token=token
            ),
        )

    def _build_service_config(
        self, config_override: dict | None = None
    ) -> QueueServiceConfig:
        """Build service configuration from environment variables and overrides.

                Operational behavior:
                        - These settings control visibility timeout, poll cadence, and worker
                            concurrency for queue processing.
                        - The queue connection identifiers are sourced from
                            `self.application_context.configuration`.

                This reads the following environment variables (Docker-friendly) and
                converts them to the appropriate types:

        - `VISIBILITY_TIMEOUT_MINUTES` (default: 5)
        - `POLL_INTERVAL_SECONDS` (default: 5)
        - `MESSAGE_TIMEOUT_MINUTES` (default: 25)
        - `CONCURRENT_WORKERS` (default: 1)

        Any `config_override` values are applied last, so callers can adjust
        behavior for local debugging/testing without changing environment.
        """

        # Get configuration from environment variables (Docker-friendly)

        # Add protective checks for environment variables
        visibility_timeout = os.getenv("VISIBILITY_TIMEOUT_MINUTES", "5")
        poll_interval = os.getenv("POLL_INTERVAL_SECONDS", "5")
        message_timeout = os.getenv("MESSAGE_TIMEOUT_MINUTES", "25")
        concurrent_workers = os.getenv("CONCURRENT_WORKERS", "1")

        # Debug print to see what we're getting (only if debug mode is enabled)
        if self.debug_mode:
            print("DEBUG - Environment variables:")
            print(
                f"  VISIBILITY_TIMEOUT_MINUTES: {visibility_timeout} (type: {type(visibility_timeout)})"
            )
            print(
                f"  POLL_INTERVAL_SECONDS: {poll_interval} (type: {type(poll_interval)})"
            )
            print(
                f"  MESSAGE_TIMEOUT_MINUTES: {message_timeout} (type: {type(message_timeout)})"
            )
            print(
                f"  CONCURRENT_WORKERS: {concurrent_workers} (type: {type(concurrent_workers)})"
            )

        config = QueueServiceConfig(
            use_entra_id=True,
            storage_account_name=self.application_context.configuration.storage_queue_account,  # type:ignore
            queue_name=self.application_context.configuration.storage_account_process_queue,  # type:ignore
            visibility_timeout_minutes=int(visibility_timeout)
            if isinstance(visibility_timeout, str)
            else visibility_timeout,
            concurrent_workers=int(concurrent_workers)
            if isinstance(concurrent_workers, str)
            else concurrent_workers,
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
        """Start the queue processing service.

        Runtime flow:
            1) Build/start the optional control API (if enabled)
            2) Start the queue worker loop (`QueueMigrationService.start_service()`)

        Lifecycle guarantees:
            - Blocks until the worker stops or an exception escapes.
            - Always attempts a graceful shutdown in `finally`.
        """
        if not self.queue_service:
            raise RuntimeError(
                "Service not initialized. Call initialize_service() first."
            )

        logger.info("Starting Queue-based Migration Service...")

        try:
            if self.control_api is None:
                try:
                    self.control_api = await self._build_control_api()
                except Exception as e:
                    logger.warning(f"Failed to build control API: {e}")
                    self.control_api = None

            if self.control_api:
                await self.control_api.start()

            # Start the service (this will run until stopped)
            await self.queue_service.start_service()
        except KeyboardInterrupt:
            logger.info("Service interrupted by user (SIGTERM/SIGINT)")
        except Exception as e:
            logger.error(f"Service error: {e}")
        finally:
            await self.shutdown_service()
            logger.info("Service stopped")

    async def shutdown_service(self):
        """Gracefully shut down the service and release resources.

        Runtime order:
            - Stop the control API first (if present)
            - Stop the queue worker
        """
        if self.control_api:
            await self.control_api.stop()
            self.control_api = None

        if self.queue_service:
            logger.info("Shutting down Queue Migration Service...")
            await self.queue_service.stop_service()
            self.queue_service = None

        logger.info("Service shutdown complete")

    async def force_stop_service(self):
        """Force immediate shutdown of the service.

        This bypasses the normal graceful stop behavior. Use when the worker loop
        is stuck or needs immediate termination.
        """
        if self.queue_service:
            logger.warning("Force stopping Queue Migration Service...")
            await self.queue_service.force_stop()
            self.queue_service = None

        logger.info("Service force stopped")

    def is_service_running(self) -> bool:
        """Return whether the queue worker service is currently running."""
        return self.queue_service is not None and self.queue_service.is_running

    def get_service_status(self) -> dict:
        """Get current service status for reporting and health checks.

        Returns a merged view of the underlying queue service status plus a
        `docker_health` field to support container health probes.
        """
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
        """Run the migration service until stopped."""
        # Starting the Queue Service
        await self.start_service()

    # Message utilities for testing and queue management

    # Main execution functions


async def run_queue_service(
    config_override: dict | None = None, debug_mode: bool = False
):
    """
    Run the queue-based migration service with Docker auto-restart support.

    Operational behavior:
        - Constructs `QueueMigrationServiceApp`, which wires the DI container and services.
        - Starts the queue worker loop and blocks until stopped.
        - On KeyboardInterrupt, performs best-effort cleanup and exits cleanly.
        - On other exceptions, attempts cleanup and re-raises so the process can
          exit non-zero (allowing Docker restart policies to take effect).
    """
    # Create service application
    app = QueueMigrationServiceApp(
        config_override=config_override,
        debug_mode=debug_mode,
    )

    try:
        # Initialize and start service
        logger.info("Starting queue service...")
        await app.run()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        # Properly stop the service before exiting
        try:
            if app.queue_service:
                await app.queue_service.stop_service()
            logger.info("Service shutdown complete")
        except Exception as cleanup_error:
            logger.warning(f"Error during cleanup: {cleanup_error}")
        logger.info("Service stopped")
        # Exit gracefully without raising the KeyboardInterrupt
    except Exception as e:
        logger.error(f"Failed to run queue service: {e}")
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
    debug_mode = False
    asyncio.run(run_queue_service(debug_mode=debug_mode))
