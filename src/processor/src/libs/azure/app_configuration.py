# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os

from azure.appconfiguration import AzureAppConfigurationClient
from azure.identity import (
    AzureCliCredential,
    AzureDeveloperCliCredential,
    DefaultAzureCredential,
    ManagedIdentityCredential,
)

# Type alias for any Azure credential type
AzureCredential = (
    DefaultAzureCredential
    | AzureCliCredential
    | AzureDeveloperCliCredential
    | ManagedIdentityCredential
)


class AppConfigurationHelper:
    """
    Helper class to manage Azure App Configuration settings.
    This class initializes the Azure App Configuration client and provides methods
    to read configuration settings and set them as environment variables.
    Attributes:
        credential (AzureCredential): Azure credential for authentication.
        app_config_endpoint (str): Endpoint for the Azure App Configuration.
        app_config_client (AzureAppConfigurationClient): Client to interact with Azure App Configuration.
    """

    credential: AzureCredential | None = None
    app_config_endpoint: str | None = None
    app_config_client: AzureAppConfigurationClient | None = None

    def __init__(
        self, app_configuration_url: str, credential: AzureCredential | None = None
    ):
        self.credential = credential or DefaultAzureCredential()
        self.app_config_endpoint = app_configuration_url
        self._initialize_client()

    def _initialize_client(self):
        if self.app_config_endpoint is None:
            raise ValueError("App Configuration Endpoint is not set.")
        if self.credential is None:
            raise ValueError("Azure credential is not set.")

        self.app_config_client = AzureAppConfigurationClient(
            self.app_config_endpoint, self.credential
        )

    def read_configuration(self):
        """
        Reads configuration settings from Azure App Configuration.
        Returns:
            list: A list of configuration settings.
        """
        if self.app_config_client is None:
            raise ValueError("App Configuration client is not initialized.")
        return self.app_config_client.list_configuration_settings()

    def read_and_set_environmental_variables(self):
        """
        Reads configuration settings from Azure App Configuration and sets them as environment variables.
        Returns:
            dict: A dictionary of environment variables set from the configuration settings.
        """
        configuration_settings = self.read_configuration()
        # Iterate through all configuration settings and set them as environment variables
        for item in configuration_settings:
            os.environ[item.key] = item.value

        return os.environ
