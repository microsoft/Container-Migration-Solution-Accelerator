import os

from azure.appconfiguration import AzureAppConfigurationClient
from azure.identity import DefaultAzureCredential


class AppConfigurationHelper:
    """
    Helper class to manage Azure App Configuration settings.
    This class initializes the Azure App Configuration client and provides methods
    to read configuration settings and set them as environment variables.
    Attributes:
        credential (DefaultAzureCredential): Azure credential for authentication.
        app_config_endpoint (str): Endpoint for the Azure App Configuration.
        app_config_client (AzureAppConfigurationClient): Client to interact with Azure App Configuration.
    """

    credential: DefaultAzureCredential = None
    app_config_endpoint: str = None
    app_config_client: AzureAppConfigurationClient = None

    def __init__(
        self, app_configuration_url: str, credential: DefaultAzureCredential = None
    ):
        self.credential = credential or DefaultAzureCredential()
        self.app_config_endpoint = app_configuration_url
        self._initialize_client()

    def _initialize_client(self):
        if self.app_config_endpoint is None:
            raise ValueError("App Configuration Endpoint is not set.")

        self.app_config_client = AzureAppConfigurationClient(
            self.app_config_endpoint, self.credential
        )

    def read_configuration(self):
        """
        Reads configuration settings from Azure App Configuration.
        Returns:
            list: A list of configuration settings.
        """
        return self.app_config_client.list_configuration_settings()

    def read_and_set_environmental_variables(self):
        """
        Reads configuration settings from Azure App Configuration and sets them as environment variables.
        Returns:
            dict: A dictionary of environment variables set from the configuration settings.
        """
        # self.read_configuration()
        for item in self.read_configuration():
            os.environ[item.key] = item.value

        return os.environ
