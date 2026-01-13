from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class _configuration_base(BaseSettings):
    """
    Base configuration class for the application.
    This class can be extended to define specific configurations.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


class _envConfiguration(_configuration_base):
    """
    Environment configuration class for the application.
    Don't change the name of this class and it's attributes.
    This class is used to load environment variable for App Configuration Endpoint from a .env file.
    """

    # APP_CONFIG_ENDPOINT
    app_configuration_url: str | None = Field(default=None)


class Configuration(_configuration_base):
    """
    Configuration class for the application.

    Add your configuration variables here. Each attribute will automatically
    map to an environment variable or Azure App Configuration key.

    Mapping Rules:
    - Environment Variable: UPPER_CASE_WITH_UNDERSCORES
    - Class Attribute: lower_case_with_underscores
    - Example: APP_LOGGING_ENABLE → app_logging_enable
    """

    # Application Logging Configuration
    app_logging_enable: bool = Field(
        default=False, description="Enable application logging"
    )
    app_logging_level: str = Field(
        default="DEBUG", description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )

    # Sample Configuration
    app_sample_variable: str = Field(
        default="Hello World!", description="Sample configuration variable"
    )

    cosmos_db_account_url: str = Field(
        default="http://<cosmos url>", alias="COSMOS_DB_ACCOUNT_URL"
    )
    cosmos_db_database_name: str = Field(
        default="<database name>", alias="COSMOS_DB_DATABASE_NAME"
    )
    cosmos_db_container_name: str = Field(
        default="<container name>", alias="COSMOS_DB_CONTAINER_NAME"
    )
    cosmos_db_control_container_name: str = Field(
        default="<control container name>",
        alias="COSMOS_DB_CONTROL_CONTAINER_NAME",
        description="Cosmos container name for process control records (kill requests, etc.)",
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

    # Add your custom configuration here:
    # Example configurations (uncomment and modify as needed):

    # Database Configuration
    # database_url: str = Field(default="sqlite:///app.db", description="Database connection URL")
    # database_pool_size: int = Field(default=5, description="Database connection pool size")

    # API Configuration
    # api_timeout: int = Field(default=30, description="API request timeout in seconds")
    # api_retry_attempts: int = Field(default=3, description="Number of API retry attempts")

    # Feature Flags
    # enable_debug_mode: bool = Field(default=False, description="Enable debug mode")
    # enable_feature_x: bool = Field(default=False, description="Enable feature X")

    # Security Configuration
    # secret_key: str = Field(default="change-me-in-production", description="Secret key for encryption")
    # jwt_expiration_hours: int = Field(default=24, description="JWT token expiration in hours")
