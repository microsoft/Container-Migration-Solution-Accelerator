from abc import ABC, abstractmethod
import inspect
import logging
import os

from dotenv import load_dotenv

from libs.application.application_configuration import Configuration, _envConfiguration
from libs.application.application_context import AppContext
from libs.azure.app_configuration import AppConfigurationHelper
from libs.base.KernelAgent import semantic_kernel_agent
from utils.credential_util import get_azure_credential

# Initialize logger
logger = logging.getLogger(__name__)


class ApplicationBase(ABC):
    sk_agent: semantic_kernel_agent
    plugins_directory: str | None = None
    app_context: AppContext | None = None

    def __init__(
        self,
        debug_mode: bool = False,
        env_file_path: str | None = None,
        custom_service_prefixes: dict[str, str] | None = None,
        use_entra_id: bool = False,
    ):
        """
        Initialize the ApplicationBase with optional debug mode.
        """
        self.debug_mode = debug_mode
        self.env_file_path = env_file_path
        self.custom_service_prefixes = custom_service_prefixes
        self.use_entra_id = use_entra_id

        """
        Initialize App Context and reading configurations.
        """
        self.app_context = AppContext()

        # Get App Configuration Endpoint from .env file
        app_config_url: str | None = _envConfiguration().app_configuration_url
        # Load environment variables from Azure App Configuration endpoint url
        if app_config_url != "" and app_config_url is not None:
            # If app_configuration_url is not None, then read the configuration from Azure App Configuration
            # and set them as environment variables

            credential = get_azure_credential()
            AppConfigurationHelper(
                app_configuration_url=app_config_url,
                credential=credential,
            ).read_and_set_environmental_variables()

            # Set the credential in app context for telemetry and other services
            self.app_context.set_credential(credential)
        else:
            # Set credential even if no app config URL
            credential = get_azure_credential()
            self.app_context.set_credential(credential)

        self.app_context.set_configuration(Configuration())

        # This allows explicit debug_mode control from main_service.py
        # if not self.debug_mode:
        #     self.debug_mode = self.app_context.configuration.app_logging_enable

    @abstractmethod
    def run(self):
        raise NotImplementedError("Run method not implemented")

    async def initialize_async(self):
        if self.debug_mode:
            logging.basicConfig(level=logging.DEBUG)
        else:
            # Ensure non-debug mode suppresses all debug messages
            logging.basicConfig(level=logging.WARNING)

        # Configure Azure package logging levels only if packages are specified
        if self.app_context.configuration.azure_logging_packages:
            azure_level = getattr(logging, self.app_context.configuration.azure_package_logging_level.upper(), logging.WARNING)
            for logger_name in filter(None, (pkg.strip() for pkg in self.app_context.configuration.azure_logging_packages.split(','))):
                logging.getLogger(logger_name).setLevel(azure_level)

        # Always suppress semantic kernel debug messages unless explicitly in debug mode
        if not self.debug_mode:
            logging.getLogger("semantic_kernel").setLevel(logging.WARNING)
            logging.getLogger("semantic_kernel.connectors").setLevel(logging.WARNING)
            logging.getLogger("semantic_kernel.connectors.ai").setLevel(logging.WARNING)

        # Detect plugins directory
        self._detect_sk_plugins_directory()

        logger.info("[SUCCESS] Application base initialized")

    def _load_env(self, env_file_path: str | None = None):
        if env_file_path:
            load_dotenv(dotenv_path=env_file_path)
            return env_file_path

        derived_class_location = self._get_derived_class_location()
        env_file_path = os.path.join(os.path.dirname(derived_class_location), ".env")
        load_dotenv(dotenv_path=env_file_path)
        return env_file_path

    def _get_derived_class_location(self):
        return inspect.getfile(self.__class__)

    def _detect_sk_plugins_directory(self):
        # SK plugin directory should be under main.py with name plugins/sk
        derived_class_location = self._get_derived_class_location()
        self.plugins_directory = os.path.join(
            os.path.dirname(derived_class_location), "plugins", "sk"
        )
