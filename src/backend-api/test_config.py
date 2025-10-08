#!/usr/bin/env python3

import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Now import and test the configuration
from app.libs.application.application_context import Configuration  # noqa: E402


def test_configuration():
    print("Testing Configuration Loading...")
    print("=" * 50)

    config = Configuration()

    # Print all configuration values
    config_values = {
        "app_logging_enable": config.app_logging_enable,
        "app_logging_level": config.app_logging_level,
        "cosmos_db_account_url": config.cosmos_db_account_url,
        "cosmos_db_database_name": config.cosmos_db_database_name,
        "cosmos_db_process_container": config.cosmos_db_process_container,
        "storage_account_name": config.storage_account_name,
        "storage_account_blob_url": config.storage_account_blob_url,
        "storage_account_queue_url": config.storage_account_queue_url,
        "storage_account_process_container": config.storage_account_process_container,
        "storage_account_process_queue": getattr(config, 'storage_account_process_queue', 'MISSING'),
    }

    for key, value in config_values.items():
        print(f"{key}: {value}")
        if value is None:
            print(f"  ❌ {key} is None!")
        elif value == "":
            print(f"  ❌ {key} is empty string!")
        else:
            print(f"  ✅ {key} has value")

    print("\n" + "=" * 50)
    print("Checking Environment Variables...")

    env_vars = [
        "APP_CONFIGURATION_URL",
        "COSMOS_DB_ACCOUNT_URL",
        "COSMOS_DB_DATABASE_NAME",
        "COSMOS_DB_PROCESS_CONTAINER",
        "STORAGE_ACCOUNT_NAME",
        "STORAGE_ACCOUNT_BLOB_URL",
        "STORAGE_ACCOUNT_QUEUE_URL",
        "STORAGE_ACCOUNT_PROCESS_CONTAINER",
        "STORAGE_ACCOUNT_PROCESS_QUEUE",
    ]

    for var in env_vars:
        value = os.environ.get(var)
        if value:
            print(f"✅ {var}={value}")
        else:
            print(f"❌ {var} not set")


if __name__ == "__main__":
    test_configuration()
