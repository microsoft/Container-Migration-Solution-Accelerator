from types import SimpleNamespace

from fastapi.testclient import TestClient

from libs.application.application_context import AppContext
from libs.base.typed_fastapi import TypedFastAPI
from routers.router_debug import router


def _make_configuration(**overrides):
    base = {
        "app_logging_enable": True,
        "app_logging_level": "INFO",
        "azure_package_logging_level": "WARNING",
        "azure_logging_packages": None,
        "cosmos_db_account_url": "https://cosmos.example.com",
        "cosmos_db_database_name": "db",
        "cosmos_db_process_container": "processes",
        "cosmos_db_process_log_container": "logs",
        "storage_account_name": "stg",
        "storage_account_blob_url": "https://blob.example.com",
        "storage_account_queue_url": "https://queue.example.com",
        "storage_account_process_container": "container",
        "storage_account_process_queue": "queue",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _build_client(config=None):
    app = TypedFastAPI()
    ctx = AppContext()
    ctx.set_configuration(config or _make_configuration())
    app.set_app_context(ctx)
    app.include_router(router)
    return TestClient(app)


class TestGetConfigDebug:
    def test_returns_200(self):
        client = _build_client()
        res = client.get("/debug/config")
        assert res.status_code == 200

    def test_returns_configuration_payload(self):
        client = _build_client()
        body = client.get("/debug/config").json()
        assert "configuration" in body
        cfg = body["configuration"]
        assert cfg["cosmos_db_database_name"] == "db"
        assert cfg["storage_account_name"] == "stg"
        assert cfg["app_logging_level"] == "INFO"

    def test_reflects_overridden_values(self):
        config = _make_configuration(storage_account_name="custom-storage")
        client = _build_client(config=config)
        body = client.get("/debug/config").json()
        assert body["configuration"]["storage_account_name"] == "custom-storage"
