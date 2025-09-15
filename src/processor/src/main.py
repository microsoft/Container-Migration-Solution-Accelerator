"""
Direct Migration Execution - Non-Queue Version

Simple direct execution of the migration process without Azure Storage Queue dependency.
Perfect for development, testing, and single-process executions.
"""

import asyncio
import logging
import os
from typing import Any
import uuid

from libs.base.ApplicationBase import ApplicationBase
from services.migration_service import MigrationEngineResult, MigrationProcessor

# Import comprehensive logging suppression
from utils.quiet_logging import suppress_verbose_logging

# Apply comprehensive verbose logging suppression
suppress_verbose_logging(debug_mode=False)  # Default to production mode

logger = logging.getLogger(__name__)


class DirectMigrationApp(ApplicationBase):
    """
    Direct migration application that runs without queue dependencies.

    This provides a simple way to execute migrations directly without
    needing Azure Storage Queue infrastructure.
    """

    def __init__(self, **kwargs):
        """Initialize the direct migration application"""
        super().__init__(**kwargs)
        self.migration_processor: MigrationProcessor | None = None

        # Update logging level based on debug mode
        if self.debug_mode:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.debug("Debug logging enabled")
        else:
            logging.getLogger().setLevel(logging.INFO)

    def run(self):
        """Implementation of abstract run method from ApplicationBase"""
        # This is synchronous - actual execution happens in run_sample_migration
        pass

    async def initialize_service(self):
        """Initialize the migration service without queue dependencies"""
        # Initialize the ApplicationBase (this sets up app_context)
        await super().initialize_async()

        logger.info("🚀 Initializing Direct Migration Service...")

        # Create migration processor
        self.migration_processor = MigrationProcessor(
            app_context=self.app_context,
            debug_mode=self.debug_mode,
            timeout_minutes=25,  # 25 minute timeout
        )

        # Initialize the processor
        await self.migration_processor.initialize()

        logger.info("✅ Direct Migration Service initialized")

    async def execute_migration(
        self,
        migration_request: dict[str, Any] | None = None,
        user_id: str = "local_user",
        process_id: str | None = None,
    ) -> MigrationEngineResult:
        """
        Execute a migration directly without queue processing

        Args:
            migration_request: Migration configuration
            user_id: User identifier
            process_id: Optional process ID (will generate one if not provided)

        Returns:
            MigrationEngineResult with execution results
        """
        if not self.migration_processor:
            raise RuntimeError(
                "Migration service not initialized. Call initialize_service() first."
            )

        # Generate process ID if not provided
        if not process_id:
            process_id = str(uuid.uuid4())

        # Use default migration request if none provided
        if not migration_request:
            migration_request = self.get_default_migration_request()

        logger.info("🎯 Starting direct migration execution")
        logger.info(f"   Process ID: {process_id}")
        logger.info(f"   User ID: {user_id}")
        logger.info(f"   Migration Request: {migration_request}")

        try:
            # Execute the migration
            result = await self.migration_processor.execute_migration(
                process_id=process_id,
                user_id=user_id,
                migration_request=migration_request,
            )

            if result.success:
                logger.info(f"✅ Migration completed successfully: {process_id}")
            else:
                logger.error(f"❌ Migration failed: {result.error_message}")

            return result

        except Exception as e:
            logger.error(f"💥 Migration execution failed with exception: {e}")
            raise

    def get_default_migration_request(self) -> dict[str, Any]:
        """Get default migration request for testing"""
        return {
            "process_id": "a54b47dd-e131-45f5-8a35-a7d17ccb3d8b",
            "user_id": "local_user",
            "container_name": "processes",  # Use processes container where files exist
            "source_file_folder": "source",  # Point to specific migration run with EKS files
            "workspace_file_folder": "workspace",
            "output_file_folder": "converted",  # Use converted folder for outputs
        }

    async def run_sample_migration(self):
        """Run a sample migration with default settings"""
        await self.initialize_service()

        logger.info("📁 Looking for files in migration folders...")

        # Use the default migration request that points to local files
        sample_request = self.get_default_migration_request()
        process_id = "a54b47dd-e131-45f5-8a35-a7d17ccb3d8b"
        sample_request["process_id"] = process_id
        sample_request["source_file_folder"] = f"{process_id}/source"
        sample_request["workspace_file_folder"] = f"{process_id}/workspace"
        sample_request["output_file_folder"] = f"{process_id}/converted"
        result = await self.execute_migration(migration_request=sample_request)
        return result


async def run_direct_migration():
    """
    Main execution function for direct migration (no queue)
    """
    # Create the application with explicit debug mode setting
    app = DirectMigrationApp(
        debug_mode=False,  # Enable debug logging and detailed tracing
        env_file_path=os.path.join(os.path.dirname(__file__), ".env"),
    )

    try:
        # Run a sample migration
        logger.info("🌟 Starting Direct Migration Service...")
        result = await app.run_sample_migration()

        if result.success:
            logger.info("🎉 Sample migration completed successfully!")
            logger.info(f"   Execution time: {result.execution_time:.2f} seconds")
            logger.info(f"   Process Status: {result.status}")
        else:
            logger.error("💔 Sample migration failed")
            logger.error(f"   Error message: {result.error_message}")
            logger.error(f"   Error classification: {result.error_classification}")

    except KeyboardInterrupt:
        logger.info("🛑 Migration interrupted by user")

    except asyncio.CancelledError:
        logger.info("🛑 Migration was cancelled during cleanup - this is normal")

    except Exception as e:
        logger.error(f"💥 Failed to run direct migration: {e}")
        # Don't re-raise during cleanup issues
        if "cancel scope" in str(e) or "TaskGroup" in str(e):
            logger.warning(
                "⚠️  Cleanup issue detected - migration likely completed successfully"
            )
        else:
            raise


# Entry point
if __name__ == "__main__":
    asyncio.run(run_direct_migration())
