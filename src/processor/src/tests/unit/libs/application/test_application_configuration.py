# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from libs.application.application_configuration import Configuration


def test_configuration_reads_alias_env_vars(monkeypatch) -> None:
    monkeypatch.setenv("COSMOS_DB_ACCOUNT_URL", "https://cosmos.example")
    monkeypatch.setenv("COSMOS_DB_DATABASE_NAME", "db1")
    monkeypatch.setenv("COSMOS_DB_CONTAINER_NAME", "c1")
    monkeypatch.setenv("STORAGE_QUEUE_NAME", "q1")

    cfg = Configuration()
    assert cfg.cosmos_db_account_url == "https://cosmos.example"
    assert cfg.cosmos_db_database_name == "db1"
    assert cfg.cosmos_db_container_name == "c1"
    assert cfg.storage_queue_name == "q1"


def test_configuration_boolean_parsing(monkeypatch) -> None:
    # pydantic-settings parses common truthy strings.
    monkeypatch.setenv("APP_LOGGING_ENABLE", "true")
    cfg = Configuration()
    assert cfg.app_logging_enable is True
