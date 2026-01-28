from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from semantic_kernel.kernel_pydantic import KernelBaseSettings


class _configuration_base(BaseSettings):
    """
    Base configuration class for the application.
    This class can be extended to define specific configurations.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # This is crucial: environment variables take precedence over .env file
        # This allows Azure App Configuration to override .env file values
        case_sensitive=False,
        env_ignore_empty=True,
    )


class Configuration(_configuration_base, KernelBaseSettings):
    """
    Configuration class for the application.
    """

    # Define your configuration variables here
    # For example:
    # database_url: str
    # api_key: str
    app_logging_enable: bool = Field(default=False)
    app_logging_level: str = Field(default="INFO")
    app_sample_variable: str = Field(default="Hello World!")

    # Azure logging configuration
    azure_package_logging_level: str = Field(default="WARNING", alias="AZURE_PACKAGE_LOGGING_LEVEL")
    azure_logging_packages: str | None = Field(default=None, alias="AZURE_LOGGING_PACKAGES")

    global_llm_service: str | None = "AzureOpenAI"
    cosmos_db_process_log_container: str | None = Field(
        default=None, env="COSMOS_DB_PROCESS_LOG_CONTAINER"
    )

    cosmos_db_account_url: str | None = Field(default=None, env="COSMOS_DB_ACCOUNT_URL")
    cosmos_db_database_name: str | None = Field(
        default=None, env="COSMOS_DB_DATABASE_NAME"
    )

    cosmos_db_process_container: str | None = Field(
        default=None, env="COSMOS_DB_PROCESS_CONTAINER"
    )

    storage_account_name: str | None = Field(default=None, env="STORAGE_ACCOUNT_NAME")
    storage_account_blob_url: str | None = Field(
        default=None, env="STORAGE_ACCOUNT_BLOB_URL"
    )
    storage_account_queue_url: str | None = Field(
        default=None, env="STORAGE_ACCOUNT_QUEUE_URL"
    )
    storage_account_process_container: str | None = Field(
        default=None, env="STORAGE_ACCOUNT_PROCESS_CONTAINER"
    )
    storage_account_process_queue: str | None = Field(
        default=None, env="STORAGE_ACCOUNT_PROCESS_QUEUE"
    )

    app_insights_conn_string: str | None = Field(
        default=None, env="APPLICATIONINSIGHTS_CONNECTION_STRING"
    )

    # Processor Control API configuration
    # In Azure Container Apps, apps call each other by name: http://<container-app-name>
    # The actual URL is set via PROCESSOR_CONTROL_URL env var from Bicep
    processor_control_url: str | None = Field(
        default="http://localhost:8080", env="PROCESSOR_CONTROL_URL"
    )
    processor_control_token: str | None = Field(
        default=None, env="PROCESSOR_CONTROL_TOKEN"
    )


class _envConfiguration(_configuration_base):
    """
    Environment configuration class for the application.
    Don't change the name of this class and it's attributes.
    This class is used to load environment variable for App Configuration Endpoint from a .env file.
    """

    # APP_CONFIG_ENDPOINT
    app_configuration_url: str | None = Field(default=None)
