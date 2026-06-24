import logging
import os
from datetime import datetime

from fastapi.middleware.cors import CORSMiddleware
from libs.base.application_base import Application_Base
from libs.base.typed_fastapi import TypedFastAPI
from libs.logging.span_filters import (
    DropASGIResponseBodySpanProcessor,
    DropCosmosDependencySpanProcessor,
)
from libs.repositories.file_repository import FileRepository
from libs.repositories.process_repository import ProcessRepository
from libs.repositories.process_status_repository import ProcessStatusRepository
from libs.sas.storage import AsyncStorageBlobHelper, AsyncStorageQueueHelper
from libs.services.implementations import (
    ConsoleLoggerService,
    HttpClientService,
    InMemoryDataService,
)
from libs.services.interfaces import IDataService, IHttpService, ILoggerService
from libs.services.process_services import ProcessService

# Import from the new locations (main branch)
from routers import router_debug, router_files, router_process
from routers.http_probes import router as http_probes

logger = logging.getLogger(__name__)

# URLs (relative paths) that should NOT generate request telemetry.
# Matches the routes registered in `routers/http_probes.py`.
# `excluded_urls` is a comma-separated substring list per the
# OpenTelemetry FastAPI instrumentation contract.
_OTEL_EXCLUDED_URLS = "health,startup"


class Application(Application_Base):
    """
    Application class that extends the base application class.
    This class can be used to implement specific application logic.
    """

    app: TypedFastAPI
    start_time = datetime.now()

    def __init__(self):
        super().__init__(env_file_path=os.path.join(os.path.dirname(__file__), ".env"))

    def initialize(self):
        """
        Initialize the application.
        This method can be overridden by subclasses to perform any necessary setup.
        """
        ############################################################
        # Initialize the FastAPI application with typed version
        ############################################################
        self.app = TypedFastAPI(
            redirect_slashes=False, title="FastAPI Application", version="1.0.0"
        )
        ######################################################################
        # Set the application context to the FastAPI app with proper typing
        ######################################################################
        self.app.set_app_context(self.application_context)

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Wire up Azure Monitor / OpenTelemetry BEFORE the routers are
        # included so that the FastAPI instrumentor can patch the app
        # while the route table is still empty. `configure_azure_monitor`
        # is a no-op (warns once) when the connection string env var is
        # absent — see `libs/logging/event_utils.py`.
        self._configure_azure_monitor()

        self.app.include_router(http_probes)
        self._register_dependencies()
        self._config_routers()
        # self._initialize_database()

        # Instrumenting AFTER routers are registered means every route is
        # automatically wrapped by the OTEL middleware.
        self._instrument_fastapi()

    def _configure_azure_monitor(self):
        """Initialise Azure Monitor OpenTelemetry exporter, if configured.

        This is the App Insights "linkage" step required by AC #1 / AC #2:
        if `APPLICATIONINSIGHTS_CONNECTION_STRING` is set in the
        container app environment (wired by Bicep — see
        `infra/main.bicep`), we hand it to `configure_azure_monitor`
        along with our two noise-suppressing span processors.

        Live Metrics is enabled so the team can watch the Maintenance
        environment in real time during demo validation.
        """
        connection_string = os.environ.get(
            "APPLICATIONINSIGHTS_CONNECTION_STRING", ""
        ).strip()
        if not connection_string:
            logger.info(
                "APPLICATIONINSIGHTS_CONNECTION_STRING not set; "
                "skipping Azure Monitor OpenTelemetry configuration."
            )
            return

        try:
            from azure.monitor.opentelemetry import configure_azure_monitor

            configure_azure_monitor(
                connection_string=connection_string,
                enable_live_metrics=True,
                span_processors=[
                    DropASGIResponseBodySpanProcessor(),
                    DropCosmosDependencySpanProcessor(),
                ],
            )
            # Do NOT log the connection string itself — it contains the
            # ingestion key. Logging only the fact of configuration.
            logger.info(
                "Azure Monitor OpenTelemetry configured (live metrics enabled)."
            )
        except Exception:  # noqa: BLE001 — telemetry must never break startup
            logger.exception(
                "Failed to configure Azure Monitor OpenTelemetry; "
                "continuing without App Insights export."
            )

    def _instrument_fastapi(self):
        """Apply the OpenTelemetry FastAPI instrumentation.

        Excludes the liveness / startup probe routes (registered in
        `routers/http_probes.py`) so probe traffic does not flood
        Application Insights with no-information request rows.
        """
        if not os.environ.get(
            "APPLICATIONINSIGHTS_CONNECTION_STRING", ""
        ).strip():
            # No exporter wired up; instrumenting is a wasted import.
            return
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(
                self.app, excluded_urls=_OTEL_EXCLUDED_URLS
            )
            logger.info(
                "FastAPIInstrumentor attached (excluded_urls=%s).",
                _OTEL_EXCLUDED_URLS,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to attach FastAPIInstrumentor; "
                "continuing without per-request telemetry."
            )

    def _config_routers(self):
        """
        Configure routers for the FastAPI application.
        This method can be overridden by subclasses to add custom routers.
        """
        ############################################################
        # Add your routers here
        ############################################################

        routers = [
            http_probes,
            router_process.router,
            router_files.router,
            router_debug.router,
        ]

        for router in routers:
            self.app.include_router(router)

    def _register_dependencies(self):
        """
        Add dependencies to the FastAPI application.
        This method can be overridden by subclasses to add custom dependencies.
        """

        # Register router business logics
        (
            # router_process_business logic
            self.application_context.add_transient(
                ProcessService, lambda: ProcessService(self.app)
            )
            .add_transient(
                AsyncStorageBlobHelper,
                lambda: AsyncStorageBlobHelper(
                    account_name=self.application_context.configuration.storage_account_name,
                ),
            )
            # Repository is thread safe.
            .add_scoped(
                ProcessStatusRepository,
                lambda: ProcessStatusRepository(
                    account_url=self.application_context.configuration.cosmos_db_account_url,
                    database_name=self.application_context.configuration.cosmos_db_database_name,
                    container_name=self.application_context.configuration.cosmos_db_process_log_container,
                ),
            )
            # Repository is thread safe.
            .add_async_singleton(
                ProcessRepository,
                lambda: ProcessRepository(
                    account_url=self.application_context.configuration.cosmos_db_account_url,
                    database_name=self.application_context.configuration.cosmos_db_database_name,
                    container_name="processes",
                ),
            )
            .add_singleton(
                FileRepository,
                lambda: FileRepository(
                    account_url=self.application_context.configuration.cosmos_db_account_url,
                    database_name=self.application_context.configuration.cosmos_db_database_name,
                    container_name="files",
                ),
            )
            .add_transient(
                AsyncStorageQueueHelper,
                lambda: AsyncStorageQueueHelper(
                    account_name=self.application_context.configuration.storage_account_name,
                ),
            )
            .add_singleton(ILoggerService, ConsoleLoggerService)
            .add_transient(IHttpService, HttpClientService)
            .add_singleton(IDataService, InMemoryDataService)
        )

    def run(self, host: str = "0.0.0.0", port: int = 8000, reload: bool = True):
        pass
