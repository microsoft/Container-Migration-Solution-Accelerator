"""Tests for libs/repositories/file_repository.py and process_repository.py."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from libs.repositories import file_repository as fr_module
from libs.repositories import process_repository as pr_module
from libs.repositories.file_repository import FileRepository
from libs.repositories.process_repository import ProcessRepository


def _no_init(self, *args, **kwargs):  # pragma: no cover - helper
    return None


class TestFileRepository:
    @pytest.mark.asyncio
    async def test_update_async_sets_updated_at_and_calls_super(self):
        with patch.object(fr_module.RepositoryBase, "__init__", _no_init):
            repo = FileRepository(
                account_url="https://x", database_name="db", container_name="c"
            )

        entity = SimpleNamespace(id="f1", updated_at=None)
        before = datetime.now(UTC) - timedelta(seconds=1)

        with patch.object(
            fr_module.RepositoryBase,
            "update_async",
            new=AsyncMock(return_value=entity),
        ) as mock_super:
            result = await repo.update_async(entity)

        after = datetime.now(UTC) + timedelta(seconds=1)
        assert result is entity
        assert isinstance(entity.updated_at, datetime)
        assert before <= entity.updated_at <= after
        mock_super.assert_awaited_once_with(entity)

    def test_init_calls_super_with_proper_args(self):
        captured = {}

        def fake_init(self, account_url, database_name, container_name):
            captured["account_url"] = account_url
            captured["database_name"] = database_name
            captured["container_name"] = container_name

        with patch.object(fr_module.RepositoryBase, "__init__", fake_init):
            FileRepository(
                account_url="https://acct.documents.azure.com",
                database_name="mydb",
                container_name="files",
            )

        assert captured == {
            "account_url": "https://acct.documents.azure.com",
            "database_name": "mydb",
            "container_name": "files",
        }


class TestProcessRepository:
    @pytest.mark.asyncio
    async def test_update_async_sets_updated_at_and_calls_super(self):
        with patch.object(pr_module.RepositoryBase, "__init__", _no_init):
            repo = ProcessRepository(
                account_url="https://x", database_name="db", container_name="c"
            )

        entity = SimpleNamespace(id="p1", updated_at=None)
        before = datetime.now(UTC) - timedelta(seconds=1)

        with patch.object(
            pr_module.RepositoryBase,
            "update_async",
            new=AsyncMock(return_value=entity),
        ) as mock_super:
            result = await repo.update_async(entity)

        after = datetime.now(UTC) + timedelta(seconds=1)
        assert result is entity
        assert isinstance(entity.updated_at, datetime)
        assert before <= entity.updated_at <= after
        mock_super.assert_awaited_once_with(entity)

    def test_init_calls_super_with_proper_args(self):
        captured = {}

        def fake_init(self, account_url, database_name, container_name):
            captured["account_url"] = account_url
            captured["database_name"] = database_name
            captured["container_name"] = container_name

        with patch.object(pr_module.RepositoryBase, "__init__", fake_init):
            ProcessRepository(
                account_url="https://acct.documents.azure.com",
                database_name="mydb",
                container_name="processes",
            )

        assert captured == {
            "account_url": "https://acct.documents.azure.com",
            "database_name": "mydb",
            "container_name": "processes",
        }
