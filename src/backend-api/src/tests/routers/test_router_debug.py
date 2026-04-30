from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers import router_debug
from libs.base.typed_fastapi import TypedFastAPI


def test_router_debug_get_config_endpoint():
    """Test the debug config endpoint returns configuration."""
    app = TypedFastAPI()
    
    # Mock the app context with configuration
    mock_config = MagicMock()
    mock_config.app_logging_enable = True
    mock_config.app_logging_level = "INFO"
    mock_config.azure_package_logging_level = "WARNING"
    mock_config.azure_logging_packages = ["azure.storage"]
    mock_config.cosmos_db_account_url = "https://account.cosmos.azure.com"
    mock_config.cosmos_db_database_name = "testdb"
    mock_config.cosmos_db_process_container = "processes"
    mock_config.cosmos_db_process_log_container = "process-logs"
    mock_config.storage_account_name = "storageaccount"
    mock_config.storage_account_blob_url = "https://storageaccount.blob.core.windows.net"
    mock_config.storage_account_queue_url = "https://storageaccount.queue.core.windows.net"
    mock_config.storage_account_process_container = "process-files"
    mock_config.storage_account_process_queue = "process-queue"
    
    mock_context = MagicMock()
    mock_context.configuration = mock_config
    app.set_app_context(mock_context)
    
    app.include_router(router_debug.router)
    
    client = TestClient(app)
    response = client.get("/debug/config")
    
    assert response.status_code == 200
    data = response.json()
    assert "configuration" in data


def test_router_debug_config_contains_all_keys():
    """Test that config endpoint returns all expected configuration keys."""
    app = TypedFastAPI()
    
    mock_config = MagicMock()
    mock_config.app_logging_enable = True
    mock_config.app_logging_level = "INFO"
    mock_config.azure_package_logging_level = "WARNING"
    mock_config.azure_logging_packages = None
    mock_config.cosmos_db_account_url = "https://account.cosmos.azure.com"
    mock_config.cosmos_db_database_name = "testdb"
    mock_config.cosmos_db_process_container = "processes"
    mock_config.cosmos_db_process_log_container = "process-logs"
    mock_config.storage_account_name = "storageaccount"
    mock_config.storage_account_blob_url = "https://storageaccount.blob.core.windows.net"
    mock_config.storage_account_queue_url = "https://storageaccount.queue.core.windows.net"
    mock_config.storage_account_process_container = "process-files"
    mock_config.storage_account_process_queue = "process-queue"
    
    mock_context = MagicMock()
    mock_context.configuration = mock_config
    app.set_app_context(mock_context)
    
    app.include_router(router_debug.router)
    
    client = TestClient(app)
    response = client.get("/debug/config")
    data = response.json()
    config = data["configuration"]
    
    expected_keys = [
        "app_logging_enable",
        "app_logging_level",
        "azure_package_logging_level",
        "azure_logging_packages",
        "cosmos_db_account_url",
        "cosmos_db_database_name",
        "cosmos_db_process_container",
        "cosmos_db_process_log_container",
        "storage_account_name",
        "storage_account_blob_url",
        "storage_account_queue_url",
        "storage_account_process_container",
        "storage_account_process_queue",
    ]
    
    for key in expected_keys:
        assert key in config


def test_router_debug_config_values_match():
    """Test that config endpoint returns correct configuration values."""
    app = TypedFastAPI()
    
    mock_config = MagicMock()
    mock_config.app_logging_enable = False
    mock_config.app_logging_level = "DEBUG"
    mock_config.azure_package_logging_level = "ERROR"
    mock_config.azure_logging_packages = None
    mock_config.cosmos_db_account_url = "https://custom.cosmos.azure.com"
    mock_config.cosmos_db_database_name = "customdb"
    mock_config.cosmos_db_process_container = "custom-processes"
    mock_config.cosmos_db_process_log_container = "custom-logs"
    mock_config.storage_account_name = "customstorage"
    mock_config.storage_account_blob_url = "https://customstorage.blob.core.windows.net"
    mock_config.storage_account_queue_url = "https://customstorage.queue.core.windows.net"
    mock_config.storage_account_process_container = "custom-files"
    mock_config.storage_account_process_queue = "custom-queue"
    
    mock_context = MagicMock()
    mock_context.configuration = mock_config
    app.set_app_context(mock_context)
    
    app.include_router(router_debug.router)
    
    client = TestClient(app)
    response = client.get("/debug/config")
    data = response.json()
    config = data["configuration"]
    
    assert config["app_logging_enable"] is False
    assert config["app_logging_level"] == "DEBUG"
    assert config["azure_package_logging_level"] == "ERROR"
    assert config["cosmos_db_account_url"] == "https://custom.cosmos.azure.com"
    assert config["cosmos_db_database_name"] == "customdb"


def test_router_debug_returns_json():
    """Test that debug endpoint returns JSON response."""
    app = TypedFastAPI()
    
    mock_config = MagicMock()
    mock_config.app_logging_enable = True
    mock_config.app_logging_level = "INFO"
    mock_config.azure_package_logging_level = "WARNING"
    mock_config.azure_logging_packages = None
    mock_config.cosmos_db_account_url = "https://account.cosmos.azure.com"
    mock_config.cosmos_db_database_name = "testdb"
    mock_config.cosmos_db_process_container = "processes"
    mock_config.cosmos_db_process_log_container = "process-logs"
    mock_config.storage_account_name = "storageaccount"
    mock_config.storage_account_blob_url = "https://storageaccount.blob.core.windows.net"
    mock_config.storage_account_queue_url = "https://storageaccount.queue.core.windows.net"
    mock_config.storage_account_process_container = "process-files"
    mock_config.storage_account_process_queue = "process-queue"
    
    mock_context = MagicMock()
    mock_context.configuration = mock_config
    app.set_app_context(mock_context)
    
    app.include_router(router_debug.router)
    
    client = TestClient(app)
    response = client.get("/debug/config")
    
    assert response.headers["content-type"] == "application/json"
