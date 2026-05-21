"""Additional tests for libs/sas/storage/blob/helper.py.

Targets the previously uncovered branches: SAS URL generation (account-key
and user-delegation paths), sync_directory, credential / account name
helpers, and miscellaneous URL builders.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def blob_service_mock():
    with patch("libs.sas.storage.blob.helper.BlobServiceClient") as svc_cls:
        yield svc_cls


def _make_helper(blob_service_mock=None, **kwargs):
    from libs.sas.storage.blob.helper import StorageBlobHelper

    return StorageBlobHelper(connection_string="conn", **kwargs)


class TestInitWithConfigObject:
    def test_init_with_object_config(self, blob_service_mock):
        from libs.sas.storage.blob.helper import StorageBlobHelper

        cfg = MagicMock()
        cfg.get = MagicMock(return_value="INFO")
        h = StorageBlobHelper(connection_string="c", config=cfg)
        # Object configs are kept as-is (line 57 branch).
        assert h.config is cfg


class TestDeleteContainerForceErrorBranches:
    def test_force_delete_inner_blob_error_continues(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = MagicMock()
        h.blob_service_client.get_container_client.return_value = cc
        # Two list_blobs calls: existence check + iteration for deletion
        b1 = MagicMock()
        b1.name = "x"
        b2 = MagicMock()
        b2.name = "y"
        cc.list_blobs.side_effect = [iter([b1, b2]), iter([b1, b2])]
        bc_ok = MagicMock()
        bc_fail = MagicMock()
        bc_fail.delete_blob.side_effect = RuntimeError("blob-err")
        # First blob fails, second succeeds
        cc.get_blob_client.side_effect = [bc_fail, bc_ok]
        # delete_container final call still succeeds
        assert h.delete_container("c", force_delete=True) is True

    def test_delete_container_blobs_present_message_no_force(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = MagicMock()
        h.blob_service_client.get_container_client.return_value = cc
        cc.list_blobs.return_value = iter([])  # Initially empty for first check
        cc.delete_container.side_effect = RuntimeError(
            "Container has blobs and cannot be deleted"
        )
        with pytest.raises(ValueError):
            h.delete_container("c", force_delete=False)


def _wire_credential(blob_service_mock, *, account_key=None, account_name="myacct",
                     credential_cls_name="DefaultAzureCredential"):
    """Make the helper's blob_service_client respond like an Azure SDK client.

    Uses a dedicated stub class per credential type so that ``type(cred).__name__``
    reflects the desired credential class without mutating the shared ``MagicMock``
    class metadata (which would leak across tests).
    """
    h = _make_helper(blob_service_mock)
    h.blob_service_client.account_name = account_name
    if credential_cls_name == "AccountKey":
        cred_cls = type("StorageSharedKeyCredential", (), {})
        cred = cred_cls()
        cred.account_key = account_key
    else:
        cred_cls = type(credential_cls_name, (), {})
        cred = cred_cls()
    h.blob_service_client.credential = cred
    return h


class TestAccountAndCredentialHelpers:
    def test_get_account_name_returns_value(self, blob_service_mock):
        h = _wire_credential(blob_service_mock, account_name="abc")
        assert h._get_account_name() == "abc"

    def test_get_account_name_handles_exception(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        # Make property access raise via PropertyMock
        type(h.blob_service_client).account_name = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        assert h._get_account_name() is None

    def test_get_account_key_from_credential(self, blob_service_mock):
        h = _wire_credential(
            blob_service_mock, account_key="key123", credential_cls_name="AccountKey"
        )
        assert h._get_account_key() == "key123"

    def test_get_account_key_from_connection_string(self, blob_service_mock):
        h = _make_helper(
            blob_service_mock,
        )
        # Replace credential with object that lacks account_key
        h.blob_service_client.credential = object()
        h._connection_string = (
            "DefaultEndpointsProtocol=https;AccountName=x;AccountKey=k=y;EndpointSuffix=core"
        )
        assert h._get_account_key() == "k=y"

    def test_get_account_key_returns_none_when_missing(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        h.blob_service_client.credential = object()
        # Force a connection string without an account key
        h._connection_string = "DefaultEndpointsProtocol=https;AccountName=x"
        assert h._get_account_key() is None

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
            ("SomeOtherCredential", "Azure AD (SomeOtherCredential)"),
        ],
    )
    def test_get_credential_type_mappings(self, blob_service_mock, name, expected):
        h = _wire_credential(blob_service_mock, credential_cls_name=name)
        assert h._get_credential_type() == expected

    def test_get_credential_type_unknown_when_no_credential_attr(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        # Replace client with one that has no `credential` attribute
        bsc = MagicMock(spec=[])  # no attributes
        h.blob_service_client = bsc
        assert h._get_credential_type() == "unknown"

    def test_get_credential_type_unknown_when_credential_is_none(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        h.blob_service_client.credential = None
        assert h._get_credential_type() == "unknown"


class TestUrlBuilders:
    def test_get_blob_url(self, blob_service_mock):
        h = _wire_credential(blob_service_mock, account_name="acc")
        url = h.get_blob_url("c", "b")
        assert url == "https://acc.blob.core.windows.net/c/b"

    def test_get_container_url(self, blob_service_mock):
        h = _wire_credential(blob_service_mock, account_name="acc")
        assert (
            h.get_container_url("ctn") == "https://acc.blob.core.windows.net/ctn"
        )

    def test_get_content_type_uses_config(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        # config is a real BlobHelperConfig instance — exercise the lookup
        assert h._get_content_type("README.txt") == "text/plain"


class TestGenerateBlobSasUrl:
    def test_account_key_path(self, blob_service_mock):
        h = _wire_credential(
            blob_service_mock,
            account_name="acct",
            account_key="abc",
            credential_cls_name="AccountKey",
        )
        with patch(
            "azure.storage.blob.generate_blob_sas", return_value="sig=token"
        ) as gen:
            url = h.generate_blob_sas_url("ctn", "blob", expiry_hours=1)
        gen.assert_called_once()
        assert url.startswith("https://acct.blob.core.windows.net/ctn/blob?")
        assert "sig=token" in url

    def test_user_delegation_path(self, blob_service_mock):
        h = _wire_credential(
            blob_service_mock,
            account_name="acct",
            account_key=None,
            credential_cls_name="DefaultAzureCredential",
        )
        h.blob_service_client.get_user_delegation_key = MagicMock(return_value="udkey")
        with patch(
            "azure.storage.blob.generate_blob_sas", return_value="sig=ud"
        ) as gen:
            url = h.generate_blob_sas_url("ctn", "blob")
        gen.assert_called_once()
        assert "sig=ud" in url

    def test_unknown_credential_raises(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        h.blob_service_client.account_name = "acct"
        h.blob_service_client.credential = None  # -> credential_type 'unknown'
        h._connection_string = "DefaultEndpointsProtocol=https;AccountName=acct"
        with pytest.raises(ValueError):
            h.generate_blob_sas_url("c", "b")

    def test_no_account_name_raises(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        # Force account_name extraction to return None
        h._get_account_name = MagicMock(return_value=None)
        with pytest.raises(ValueError):
            h.generate_blob_sas_url("c", "b")

    def test_user_delegation_key_403_raises_value_error(self, blob_service_mock):
        h = _wire_credential(
            blob_service_mock,
            account_name="acct",
            account_key=None,
            credential_cls_name="DefaultAzureCredential",
        )
        h.blob_service_client.get_user_delegation_key = MagicMock(
            side_effect=RuntimeError("403 Forbidden")
        )
        with pytest.raises(ValueError):
            h.generate_blob_sas_url("c", "b")

    def test_user_delegation_key_401_raises_value_error(self, blob_service_mock):
        h = _wire_credential(
            blob_service_mock,
            account_name="acct",
            account_key=None,
            credential_cls_name="DefaultAzureCredential",
        )
        h.blob_service_client.get_user_delegation_key = MagicMock(
            side_effect=RuntimeError("401 Unauthorized")
        )
        with pytest.raises(ValueError):
            h.generate_blob_sas_url("c", "b")

    def test_user_delegation_key_other_error_wrapped(self, blob_service_mock):
        h = _wire_credential(
            blob_service_mock,
            account_name="acct",
            account_key=None,
            credential_cls_name="DefaultAzureCredential",
        )
        h.blob_service_client.get_user_delegation_key = MagicMock(
            side_effect=RuntimeError("network down")
        )
        with pytest.raises(ValueError):
            h.generate_blob_sas_url("c", "b")


class TestGenerateContainerSasUrl:
    def test_account_key_path(self, blob_service_mock):
        h = _wire_credential(
            blob_service_mock,
            account_name="acct",
            account_key="abc",
            credential_cls_name="AccountKey",
        )
        with patch(
            "azure.storage.blob.generate_container_sas", return_value="sig=ctk"
        ):
            url = h.generate_container_sas_url("ctn", expiry_hours=2)
        assert url.startswith("https://acct.blob.core.windows.net/ctn?")
        assert "sig=ctk" in url

    def test_user_delegation_path(self, blob_service_mock):
        h = _wire_credential(
            blob_service_mock,
            account_name="acct",
            account_key=None,
            credential_cls_name="DefaultAzureCredential",
        )
        h.blob_service_client.get_user_delegation_key = MagicMock(return_value="udkey")
        with patch(
            "azure.storage.blob.generate_container_sas", return_value="sig=udc"
        ):
            url = h.generate_container_sas_url("ctn")
        assert "sig=udc" in url

    def test_unknown_credential_raises(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        h.blob_service_client.account_name = "acct"
        h.blob_service_client.credential = None
        h._connection_string = "DefaultEndpointsProtocol=https;AccountName=acct"
        with pytest.raises(ValueError):
            h.generate_container_sas_url("c")

    def test_no_account_name_raises(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        h._get_account_name = MagicMock(return_value=None)
        with pytest.raises(ValueError):
            h.generate_container_sas_url("c")

    def test_user_delegation_key_403_raises_value_error(self, blob_service_mock):
        h = _wire_credential(
            blob_service_mock,
            account_name="acct",
            account_key=None,
            credential_cls_name="DefaultAzureCredential",
        )
        h.blob_service_client.get_user_delegation_key = MagicMock(
            side_effect=RuntimeError("403 Forbidden")
        )
        with pytest.raises(ValueError):
            h.generate_container_sas_url("c")

    def test_user_delegation_key_401_raises_value_error(self, blob_service_mock):
        h = _wire_credential(
            blob_service_mock,
            account_name="acct",
            account_key=None,
            credential_cls_name="DefaultAzureCredential",
        )
        h.blob_service_client.get_user_delegation_key = MagicMock(
            side_effect=RuntimeError("401 Unauthorized")
        )
        with pytest.raises(ValueError):
            h.generate_container_sas_url("c")

    def test_user_delegation_key_other_error_wrapped(self, blob_service_mock):
        h = _wire_credential(
            blob_service_mock,
            account_name="acct",
            account_key=None,
            credential_cls_name="DefaultAzureCredential",
        )
        h.blob_service_client.get_user_delegation_key = MagicMock(
            side_effect=RuntimeError("oops")
        )
        with pytest.raises(ValueError):
            h.generate_container_sas_url("c")


class TestSyncDirectory:
    def test_missing_local_directory_raises(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        with pytest.raises(FileNotFoundError):
            h.sync_directory("Z:/no/such/dir", "c")

    def test_uploads_new_files(self, blob_service_mock, tmp_path):
        h = _make_helper(blob_service_mock)
        f1 = tmp_path / "a.txt"
        f1.write_text("hello")
        h.blob_exists = MagicMock(return_value=False)
        h.upload_file = MagicMock(return_value=True)
        result = h.sync_directory(str(tmp_path), "c", blob_prefix="pre/")
        assert result["total_files"] == 1
        assert "a.txt" in result["uploaded"]
        h.upload_file.assert_called_once()

    def test_skips_excluded_patterns(self, blob_service_mock, tmp_path):
        h = _make_helper(blob_service_mock)
        (tmp_path / "x.tmp").write_text("a")
        (tmp_path / "y.txt").write_text("b")
        h.blob_exists = MagicMock(return_value=False)
        h.upload_file = MagicMock(return_value=True)
        result = h.sync_directory(
            str(tmp_path), "c", exclude_patterns=["*.tmp"]
        )
        assert "x.tmp" in result["skipped"]
        assert "y.txt" in result["uploaded"]

    def test_skips_when_blob_newer(self, blob_service_mock, tmp_path):
        from datetime import datetime, timedelta

        h = _make_helper(blob_service_mock)
        f = tmp_path / "a.txt"
        f.write_text("x")
        h.blob_exists = MagicMock(return_value=True)
        h.get_blob_properties = MagicMock(
            return_value={"last_modified": datetime.now() + timedelta(hours=1)}
        )
        result = h.sync_directory(str(tmp_path), "c")
        assert "a.txt" in result["skipped"]

    def test_collects_errors(self, blob_service_mock, tmp_path):
        h = _make_helper(blob_service_mock)
        f = tmp_path / "a.txt"
        f.write_text("x")
        h.blob_exists = MagicMock(side_effect=RuntimeError("network"))
        h.upload_file = MagicMock()
        result = h.sync_directory(str(tmp_path), "c")
        assert any("a.txt" in err for err in result["errors"])

    def test_records_failed_upload(self, blob_service_mock, tmp_path):
        h = _make_helper(blob_service_mock)
        f = tmp_path / "a.txt"
        f.write_text("x")
        h.blob_exists = MagicMock(return_value=False)
        h.upload_file = MagicMock(return_value=False)
        result = h.sync_directory(str(tmp_path), "c")
        assert any("a.txt" in err for err in result["errors"])
