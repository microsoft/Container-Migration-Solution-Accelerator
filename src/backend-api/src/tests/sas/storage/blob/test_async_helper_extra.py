"""Additional tests for libs/sas/storage/blob/async_helper.py.

Targets the previously uncovered SAS URL generators, credential / account
helpers, and the inner failure branches of delete_container.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _AsyncIter:
    def __init__(self, items):
        self._items = list(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


@pytest.fixture
def blob_service_mock():
    with patch(
        "libs.sas.storage.blob.async_helper.BlobServiceClient"
    ) as svc_cls:
        yield svc_cls


def _wire(svc_cls):
    svc_instance = MagicMock()
    svc_cls.from_connection_string.return_value = svc_instance
    svc_cls.return_value = svc_instance
    svc_instance.close = AsyncMock()
    return svc_instance


def _blob_obj(name="f.txt"):
    b = MagicMock()
    b.name = name
    return b


class TestInitWithObjectConfig:
    def test_object_config_kept_as_is(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        cfg = MagicMock()
        cfg.get = MagicMock(return_value="INFO")
        h = AsyncStorageBlobHelper(connection_string="c", config=cfg)
        assert h.config is cfg


class TestDeleteContainerInnerFailures:
    @pytest.mark.asyncio
    async def test_force_delete_inner_blob_error_continues(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        svc = _wire(blob_service_mock)
        cc = MagicMock()
        svc.get_container_client.return_value = cc
        # Two iterations of list_blobs: existence + delete pass
        b1, b2 = _blob_obj("x"), _blob_obj("y")
        cc.list_blobs = MagicMock(
            side_effect=[_AsyncIter([b1, b2]), _AsyncIter([b1, b2])]
        )
        ok = MagicMock()
        ok.delete_blob = AsyncMock(return_value=None)
        bad = MagicMock()
        bad.delete_blob = AsyncMock(side_effect=RuntimeError("boom"))
        cc.get_blob_client.side_effect = [bad, ok]
        cc.delete_container = AsyncMock(return_value=None)
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h.delete_container("c", force_delete=True) is True


def _wire_credential(svc_cls, *, account_key=None, account_name="myacct",
                     credential_cls_name="DefaultAzureCredential"):
    svc = _wire(svc_cls)
    svc.account_name = account_name
    if credential_cls_name == "AccountKey":
        cred = MagicMock()
        cred.account_key = account_key
        type(cred).__name__ = "StorageSharedKeyCredential"
    else:
        cred = MagicMock(spec=[])
        type(cred).__name__ = credential_cls_name
    svc.credential = cred
    return svc


class TestAccountAndCredentialHelpers:
    @pytest.mark.asyncio
    async def test_get_account_name_returns_value(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire_credential(blob_service_mock, account_name="abc")
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h._get_account_name() == "abc"

    @pytest.mark.asyncio
    async def test_get_account_key_from_credential(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire_credential(
            blob_service_mock,
            account_key="key123",
            credential_cls_name="AccountKey",
        )
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h._get_account_key() == "key123"

    @pytest.mark.asyncio
    async def test_get_account_key_from_connection_string(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        svc = _wire(blob_service_mock)
        svc.credential = object()
        conn = (
            "DefaultEndpointsProtocol=https;AccountName=x;AccountKey=k=v;"
            "EndpointSuffix=core.windows.net"
        )
        async with AsyncStorageBlobHelper(connection_string=conn) as h:
            assert await h._get_account_key() == "k=v"

    @pytest.mark.asyncio
    async def test_get_account_key_returns_none_when_no_match(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        svc = _wire(blob_service_mock)
        svc.credential = object()
        async with AsyncStorageBlobHelper(connection_string="AccountName=x") as h:
            assert await h._get_account_key() is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("StorageSharedKeyCredential", "Storage Account Key"),
            ("DefaultAzureCredential", "DefaultAzureCredential"),
            ("ManagedIdentityCredential", "Managed Identity"),
            ("AzureCliCredential", "Azure CLI"),
            ("EnvironmentCredential", "Environment Variables"),
            ("WorkloadIdentityCredential", "Workload Identity"),
            ("ChainedTokenCredential", "Chained Token Credential"),
            ("WeirdCustomCredential", "Azure AD (WeirdCustomCredential)"),
        ],
    )
    async def test_credential_type_mappings(
        self, blob_service_mock, name, expected
    ):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire_credential(blob_service_mock, credential_cls_name=name)
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h._get_credential_type() == expected

    @pytest.mark.asyncio
    async def test_credential_type_unknown_when_no_credential_attr(
        self, blob_service_mock
    ):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        svc = MagicMock(spec=["close", "get_container_client"])
        svc.close = AsyncMock()
        blob_service_mock.from_connection_string.return_value = svc
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h._get_credential_type() == "unknown"

    @pytest.mark.asyncio
    async def test_credential_type_unknown_when_credential_is_none(
        self, blob_service_mock
    ):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        svc = _wire(blob_service_mock)
        svc.credential = None
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h._get_credential_type() == "unknown"


class TestGenerateBlobSasUrlAsync:
    @pytest.mark.asyncio
    async def test_account_key_path(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire_credential(
            blob_service_mock,
            account_name="acct",
            account_key="abc",
            credential_cls_name="AccountKey",
        )
        with patch(
            "azure.storage.blob.generate_blob_sas", return_value="sig=token"
        ):
            async with AsyncStorageBlobHelper(connection_string="c") as h:
                url = await h.generate_blob_sas_url("ctn", "blob")
        assert "sig=token" in url

    @pytest.mark.asyncio
    async def test_user_delegation_path(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        svc = _wire_credential(
            blob_service_mock,
            account_name="acct",
            account_key=None,
            credential_cls_name="DefaultAzureCredential",
        )
        svc.get_user_delegation_key = AsyncMock(return_value="udkey")
        with patch(
            "azure.storage.blob.generate_blob_sas", return_value="sig=ud"
        ):
            async with AsyncStorageBlobHelper(connection_string="c") as h:
                url = await h.generate_blob_sas_url("ctn", "blob")
        assert "sig=ud" in url

    @pytest.mark.asyncio
    async def test_unknown_credential_raises(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        svc = _wire(blob_service_mock)
        svc.account_name = "acct"
        svc.credential = None
        async with AsyncStorageBlobHelper(connection_string="AccountName=acct") as h:
            with pytest.raises(ValueError):
                await h.generate_blob_sas_url("c", "b")

    @pytest.mark.asyncio
    async def test_no_account_name_raises(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire(blob_service_mock)
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            h._get_account_name = AsyncMock(return_value=None)
            with pytest.raises(ValueError):
                await h.generate_blob_sas_url("c", "b")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "msg",
        ["403 Forbidden", "401 Unauthorized", "network down"],
    )
    async def test_delegation_key_errors_wrapped(self, blob_service_mock, msg):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        svc = _wire_credential(
            blob_service_mock,
            account_name="acct",
            credential_cls_name="DefaultAzureCredential",
        )
        svc.get_user_delegation_key = AsyncMock(side_effect=RuntimeError(msg))
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            with pytest.raises(ValueError):
                await h.generate_blob_sas_url("c", "b")


class TestGenerateContainerSasUrlAsync:
    @pytest.mark.asyncio
    async def test_account_key_path(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire_credential(
            blob_service_mock,
            account_name="acct",
            account_key="abc",
            credential_cls_name="AccountKey",
        )
        with patch(
            "azure.storage.blob.generate_container_sas", return_value="sig=ctk"
        ):
            async with AsyncStorageBlobHelper(connection_string="c") as h:
                url = await h.generate_container_sas_url("ctn")
        assert "sig=ctk" in url

    @pytest.mark.asyncio
    async def test_user_delegation_path(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        svc = _wire_credential(
            blob_service_mock,
            account_name="acct",
            credential_cls_name="DefaultAzureCredential",
        )
        svc.get_user_delegation_key = AsyncMock(return_value="udkey")
        with patch(
            "azure.storage.blob.generate_container_sas",
            return_value="sig=udc",
        ):
            async with AsyncStorageBlobHelper(connection_string="c") as h:
                url = await h.generate_container_sas_url("ctn")
        assert "sig=udc" in url

    @pytest.mark.asyncio
    async def test_unknown_credential_raises(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        svc = _wire(blob_service_mock)
        svc.account_name = "acct"
        svc.credential = None
        async with AsyncStorageBlobHelper(connection_string="AccountName=acct") as h:
            with pytest.raises(ValueError):
                await h.generate_container_sas_url("c")

    @pytest.mark.asyncio
    async def test_no_account_name_raises(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire(blob_service_mock)
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            h._get_account_name = AsyncMock(return_value=None)
            with pytest.raises(ValueError):
                await h.generate_container_sas_url("c")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "msg",
        ["403 Forbidden", "401 Unauthorized", "transient error"],
    )
    async def test_delegation_key_errors_wrapped(self, blob_service_mock, msg):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        svc = _wire_credential(
            blob_service_mock,
            account_name="acct",
            credential_cls_name="DefaultAzureCredential",
        )
        svc.get_user_delegation_key = AsyncMock(side_effect=RuntimeError(msg))
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            with pytest.raises(ValueError):
                await h.generate_container_sas_url("c")
