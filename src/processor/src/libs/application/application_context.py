from azure.identity import (
    AzureCliCredential,
    AzureDeveloperCliCredential,
    DefaultAzureCredential,
    ManagedIdentityCredential,
)

from libs.application.application_configuration import Configuration

# Type alias for any Azure credential type
AzureCredential = (
    DefaultAzureCredential
    | AzureCliCredential
    | AzureDeveloperCliCredential
    | ManagedIdentityCredential
)


class AppContext:
    """
    Application context that holds the configuration and credentials.
    It can be extended to include more application-specific context as needed.
    Attributes:
        config (Configuration): The configuration settings for the application.
        credential (DefaultAzureCredential): The Azure credential used for authentication.
    Methods:
        set_configuration(config: Configuration): Set the configuration for the application context.
        set_credential(credential: DefaultAzureCredential): Set the Azure credential for the application context.
    """

    def __init__(self):
        """Initialize the AppContext with default values."""
        self.configuration: Configuration | None = None
        self.credential: AzureCredential | None = None

    def set_configuration(self, config: Configuration):
        """
        Set the configuration for the application context.
        """
        self.configuration = config

    def set_credential(self, credential: AzureCredential):
        """
        Set the Azure credential for the application context.
        """
        self.credential = credential
