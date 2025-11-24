from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class _configuration_base(BaseSettings):
    """
    Base configuration class for the application.
    This class can be extended to define specific configurations.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_prefix="",
        populate_by_name=True,  # This allows reading by both field name and alias
    )


class Configuration(_configuration_base):
    """
    Configuration class for the application.
    """

    # Define your configuration variables here
    # For example:
    # database_url: str
    # api_key: str
    app_logging_enable: bool = Field(default=False, alias="APP_LOGGING_ENABLE")
    app_logging_level: str = Field(default="INFO", alias="APP_LOGGING_LEVEL")
    
    # Azure logging configuration
    azure_package_logging_level: str = Field(default="WARNING", alias="AZURE_PACKAGE_LOGGING_LEVEL")
    azure_logging_packages: str | None = Field(default=None, alias="AZURE_LOGGING_PACKAGES")
    cosmos_db_account_url: str = Field(
        default="http://<cosmos url>", alias="COSMOS_DB_ACCOUNT_URL"
    )
    cosmos_db_database_name: str = Field(
        default="<database name>", alias="COSMOS_DB_DATABASE_NAME"
    )
    cosmos_db_container_name: str = Field(
        default="<container name>", alias="COSMOS_DB_CONTAINER_NAME"
    )
    storage_queue_account: str = Field(
        default="http://<storage queue url>", alias="STORAGE_QUEUE_ACCOUNT"
    )
    storage_account_process_queue: str = Field(
        default="http://<storage account process queue url>",
        alias="STORAGE_ACCOUNT_PROCESS_QUEUE",
    )
    storage_queue_name: str = Field(
        default="processes-queue", alias="STORAGE_QUEUE_NAME"
    )


class _envConfiguration(_configuration_base):
    """
    Environment configuration class for the application.
    Don't change the name of this class and it's attributes.
    This class is used to load environment variable for App Configuration Endpoint from a .env file.
    """

    # APP_CONFIG_ENDPOINT
    app_configuration_url: str | None = Field(default=None)
