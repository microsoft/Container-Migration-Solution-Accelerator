"""Tests for libs/sas/storage/blob/helper.py."""

from unittest.mock import MagicMock, patch

import pytest
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError


@pytest.fixture
def blob_service_mock():
    with patch("libs.sas.storage.blob.helper.BlobServiceClient") as svc_cls:
        yield svc_cls


def _make_helper(blob_service_mock, **kwargs):
    from libs.sas.storage.blob.helper import StorageBlobHelper

    return StorageBlobHelper(connection_string="conn", **kwargs)


def _container_client(helper):
    cc = MagicMock()
    helper.blob_service_client.get_container_client.return_value = cc
    return cc


def _blob_client(container_client):
    bc = MagicMock()
    container_client.get_blob_client.return_value = bc
    return bc


class TestInit:
    def test_init_with_connection_string(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        blob_service_mock.from_connection_string.assert_called_once()
        assert h._connection_string == "conn"

    def test_init_with_account_and_credential(self, blob_service_mock):
        from libs.sas.storage.blob.helper import StorageBlobHelper

        StorageBlobHelper(account_name="acct", credential=MagicMock())
        blob_service_mock.assert_called()

    def test_init_with_account_only_uses_default_credential(self, blob_service_mock):
        from libs.sas.storage.blob.helper import StorageBlobHelper

        with patch("libs.sas.storage.blob.helper.DefaultAzureCredential") as cred:
            StorageBlobHelper(account_name="acct")
            cred.assert_called_once()

    def test_init_no_args_raises(self, blob_service_mock):
        from libs.sas.storage.blob.helper import StorageBlobHelper

        with pytest.raises(ValueError):
            StorageBlobHelper()

    def test_init_with_dict_config(self, blob_service_mock):
        from libs.sas.storage.blob.helper import StorageBlobHelper

        with patch("libs.sas.storage.blob.config.create_config") as cc:
            cc.return_value = {"logging_level": "INFO"}
            StorageBlobHelper(connection_string="c", config={"x": 1})
            cc.assert_called_once()

    def test_init_failure_propagates(self, blob_service_mock):
        from libs.sas.storage.blob.helper import StorageBlobHelper

        blob_service_mock.from_connection_string.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            StorageBlobHelper(connection_string="c")


class TestContainerOps:
    def test_create_container_success(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        _container_client(h)
        assert h.create_container("c") is True

    def test_create_container_exists(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        cc.create_container.side_effect = ResourceExistsError("e")
        assert h.create_container("c") is False

    def test_create_container_error(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        cc.create_container.side_effect = RuntimeError("x")
        with pytest.raises(RuntimeError):
            h.create_container("c")

    def test_delete_container_empty(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        cc.list_blobs.return_value = iter([])
        assert h.delete_container("c") is True

    def test_delete_container_non_empty_without_force(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        cc.list_blobs.return_value = iter([MagicMock(name="b1")])
        with pytest.raises(ValueError):
            h.delete_container("c", force_delete=False)

    def test_delete_container_force_with_blobs(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        b1 = MagicMock()
        b1.name = "x"
        cc.list_blobs.side_effect = [iter([b1]), iter([b1])]
        bc = MagicMock()
        cc.get_blob_client.return_value = bc
        assert h.delete_container("c", force_delete=True) is True

    def test_delete_container_not_found(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        cc.list_blobs.return_value = iter([])
        cc.delete_container.side_effect = ResourceNotFoundError("nf")
        assert h.delete_container("c") is False

    def test_list_containers(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        c = MagicMock()
        c.name = "x"
        c.last_modified = None
        c.etag = "e"
        c.public_access = None
        c.metadata = {"k": "v"}
        h.blob_service_client.list_containers.return_value = iter([c])
        result = h.list_containers(include_metadata=True)
        assert result[0]["name"] == "x"
        assert result[0]["metadata"] == {"k": "v"}

    def test_list_containers_error(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        h.blob_service_client.list_containers.side_effect = RuntimeError("x")
        with pytest.raises(RuntimeError):
            h.list_containers()

    def test_container_exists_true(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        _container_client(h)
        assert h.container_exists("c") is True

    def test_container_exists_false(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        cc.get_container_properties.side_effect = ResourceNotFoundError("nf")
        assert h.container_exists("c") is False

    def test_container_exists_other_error(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        cc.get_container_properties.side_effect = RuntimeError("x")
        with pytest.raises(RuntimeError):
            h.container_exists("c")


class TestBlobUpload:
    def test_upload_blob_success(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        _blob_client(cc)
        assert h.upload_blob("c", "b", b"data") is True

    def test_upload_blob_error(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        bc = _blob_client(cc)
        bc.upload_blob.side_effect = RuntimeError("x")
        with pytest.raises(RuntimeError):
            h.upload_blob("c", "b", b"data")

    def test_upload_file_not_found(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        with pytest.raises(FileNotFoundError):
            h.upload_file("c", "b", "Z:/nope/missing.txt")

    def test_upload_file_success(self, blob_service_mock, tmp_path):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        _blob_client(cc)
        f = tmp_path / "x.txt"
        f.write_text("hi")
        assert h.upload_file("c", "b", str(f)) is True


class TestBlobDownload:
    def test_download_blob(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        bc = _blob_client(cc)
        stream = MagicMock()
        stream.readall.return_value = b"data"
        bc.download_blob.return_value = stream
        assert h.download_blob("c", "b") == b"data"

    def test_download_blob_not_found(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        bc = _blob_client(cc)
        bc.download_blob.side_effect = ResourceNotFoundError("nf")
        with pytest.raises(ResourceNotFoundError):
            h.download_blob("c", "b")

    def test_download_blob_other_error(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        bc = _blob_client(cc)
        bc.download_blob.side_effect = RuntimeError("x")
        with pytest.raises(RuntimeError):
            h.download_blob("c", "b")

    def test_download_blob_to_file(self, blob_service_mock, tmp_path):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        bc = _blob_client(cc)
        stream = MagicMock()
        stream.readall.return_value = b"data"
        bc.download_blob.return_value = stream
        out = tmp_path / "sub" / "f.bin"
        assert h.download_blob_to_file("c", "b", str(out)) is True
        assert out.read_bytes() == b"data"

    def test_download_blob_to_file_error(self, blob_service_mock, tmp_path):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        bc = _blob_client(cc)
        bc.download_blob.side_effect = RuntimeError("x")
        with pytest.raises(RuntimeError):
            h.download_blob_to_file("c", "b", str(tmp_path / "x.bin"))


class TestBlobMgmt:
    def test_delete_blob(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        _blob_client(cc)
        assert h.delete_blob("c", "b") is True

    def test_delete_blob_not_found(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        bc = _blob_client(cc)
        bc.delete_blob.side_effect = ResourceNotFoundError("nf")
        assert h.delete_blob("c", "b") is False

    def test_delete_blob_other_error(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        bc = _blob_client(cc)
        bc.delete_blob.side_effect = RuntimeError("x")
        with pytest.raises(RuntimeError):
            h.delete_blob("c", "b")

    def test_copy_blob(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        src_bc = MagicMock()
        src_bc.url = "src"
        dest_bc = MagicMock()
        dest_bc.start_copy_from_url.return_value = {"copy_status": "success"}
        h.blob_service_client.get_blob_client.side_effect = [src_bc, dest_bc]
        assert h.copy_blob("a", "b", "c", "d", metadata={"k": "v"}) is True

    def test_copy_blob_pending(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        src_bc = MagicMock()
        dest_bc = MagicMock()
        dest_bc.start_copy_from_url.return_value = {"copy_status": "pending"}
        h.blob_service_client.get_blob_client.side_effect = [src_bc, dest_bc]
        assert h.copy_blob("a", "b", "c", "d") is True

    def test_copy_blob_error(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        h.blob_service_client.get_blob_client.side_effect = RuntimeError("x")
        with pytest.raises(RuntimeError):
            h.copy_blob("a", "b", "c", "d")

    def test_move_blob_success(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        h.copy_blob = MagicMock(return_value=True)
        h.delete_blob = MagicMock(return_value=True)
        assert h.move_blob("a", "b", "c", "d") is True

    def test_move_blob_copy_failed(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        h.copy_blob = MagicMock(return_value=False)
        assert h.move_blob("a", "b", "c", "d") is False

    def test_move_blob_error(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        h.copy_blob = MagicMock(side_effect=RuntimeError("x"))
        with pytest.raises(RuntimeError):
            h.move_blob("a", "b", "c", "d")

    def test_blob_exists_true(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        _blob_client(cc)
        assert h.blob_exists("c", "b") is True

    def test_blob_exists_false(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        bc = _blob_client(cc)
        bc.get_blob_properties.side_effect = ResourceNotFoundError("nf")
        assert h.blob_exists("c", "b") is False

    def test_blob_exists_error(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        bc = _blob_client(cc)
        bc.get_blob_properties.side_effect = RuntimeError("x")
        with pytest.raises(RuntimeError):
            h.blob_exists("c", "b")


def _blob_obj(name="f.txt"):
    b = MagicMock()
    b.name = name
    b.size = 10
    b.last_modified = None
    b.etag = "e"
    b.content_settings = None
    b.blob_tier = None
    b.blob_type = None
    b.metadata = {"k": "v"}
    b.snapshot = None
    return b


class TestListAndProps:
    def test_list_blobs(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        cc.list_blobs.return_value = iter([_blob_obj()])
        result = h.list_blobs("c", include_metadata=True)
        assert result[0]["name"] == "f.txt"
        assert result[0]["metadata"] == {"k": "v"}

    def test_list_blobs_error(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        cc.list_blobs.side_effect = RuntimeError("x")
        with pytest.raises(RuntimeError):
            h.list_blobs("c")

    def test_list_blobs_hierarchical(self, blob_service_mock):
        from azure.storage.blob import BlobPrefix

        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        prefix = MagicMock(spec=BlobPrefix)
        prefix.name = "dir/"
        cc.walk_blobs.return_value = iter([prefix, _blob_obj("dir/file.txt")])
        result = h.list_blobs_hierarchical("c", prefix="dir/")
        assert len(result["prefixes"]) == 1
        assert len(result["blobs"]) == 1

    def test_list_blobs_hierarchical_error(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        cc.walk_blobs.side_effect = RuntimeError("x")
        with pytest.raises(RuntimeError):
            h.list_blobs_hierarchical("c")

    def test_get_blob_properties(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        bc = _blob_client(cc)
        props = MagicMock()
        props.size = 7
        props.last_modified = None
        props.etag = "e"
        props.content_settings = None
        props.blob_tier = None
        props.blob_type = None
        props.metadata = {}
        props.creation_time = None
        props.lease = None
        bc.get_blob_properties.return_value = props
        result = h.get_blob_properties("c", "b")
        assert result["size"] == 7
        assert result["lease_status"] is None

    def test_get_blob_properties_error(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        bc = _blob_client(cc)
        bc.get_blob_properties.side_effect = RuntimeError("x")
        with pytest.raises(RuntimeError):
            h.get_blob_properties("c", "b")

    def test_set_blob_metadata(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        _blob_client(cc)
        assert h.set_blob_metadata("c", "b", {"k": "v"}) is True

    def test_set_blob_metadata_error(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        bc = _blob_client(cc)
        bc.set_blob_metadata.side_effect = RuntimeError("x")
        with pytest.raises(RuntimeError):
            h.set_blob_metadata("c", "b", {})


class TestBatch:
    def test_upload_multiple_files_mixed(self, blob_service_mock, tmp_path):
        h = _make_helper(blob_service_mock)
        good = tmp_path / "g.txt"
        good.write_text("x")
        h.upload_file = MagicMock(return_value=True)
        results = h.upload_multiple_files("c", [str(good), "Z:/nope/missing.txt"])
        assert results[str(good)] is True
        assert results["Z:/nope/missing.txt"] is False

    def test_upload_multiple_files_upload_error(self, blob_service_mock, tmp_path):
        h = _make_helper(blob_service_mock)
        f = tmp_path / "g.txt"
        f.write_text("x")
        h.upload_file = MagicMock(side_effect=RuntimeError("x"))
        results = h.upload_multiple_files("c", [str(f)])
        assert results[str(f)] is False

    def test_download_multiple_blobs(self, blob_service_mock, tmp_path):
        h = _make_helper(blob_service_mock)
        h.download_blob_to_file = MagicMock(return_value=True)
        results = h.download_multiple_blobs("c", ["a.txt", "b.txt"], str(tmp_path))
        assert all(results.values())

    def test_download_multiple_blobs_error(self, blob_service_mock, tmp_path):
        h = _make_helper(blob_service_mock)
        h.download_blob_to_file = MagicMock(side_effect=RuntimeError("x"))
        results = h.download_multiple_blobs("c", ["a.txt"], str(tmp_path))
        assert results["a.txt"] is False

    def test_delete_multiple_blobs(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        h.delete_blob = MagicMock(return_value=True)
        results = h.delete_multiple_blobs("c", ["a", "b"])
        assert all(results.values())

    def test_delete_multiple_blobs_error(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        h.delete_blob = MagicMock(side_effect=RuntimeError("x"))
        results = h.delete_multiple_blobs("c", ["a"])
        assert results["a"] is False


class TestAdvanced:
    def test_set_blob_tier(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        _blob_client(cc)
        assert h.set_blob_tier("c", "b", "Cool") is True

    def test_set_blob_tier_error(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        bc = _blob_client(cc)
        bc.set_standard_blob_tier.side_effect = RuntimeError("x")
        with pytest.raises(RuntimeError):
            h.set_blob_tier("c", "b", "Cool")

    def test_create_snapshot(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        bc = _blob_client(cc)
        bc.create_snapshot.return_value = {"snapshot": "2024-01-01"}
        assert h.create_snapshot("c", "b") == "2024-01-01"

    def test_create_snapshot_error(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        bc = _blob_client(cc)
        bc.create_snapshot.side_effect = RuntimeError("x")
        with pytest.raises(RuntimeError):
            h.create_snapshot("c", "b")

    def test_list_blob_snapshots(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        snap = _blob_obj("b")
        snap.snapshot = "ts"
        cc.list_blobs.return_value = iter([snap])
        result = h.list_blob_snapshots("c", "b")
        assert result[0]["snapshot"] == "ts"

    def test_list_blob_snapshots_error(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        cc = _container_client(h)
        cc.list_blobs.side_effect = RuntimeError("x")
        with pytest.raises(RuntimeError):
            h.list_blob_snapshots("c", "b")

    def test_search_blobs(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        h.list_blobs = MagicMock(
            return_value=[
                {"name": "alpha.txt", "metadata": {"tag": "x"}},
                {"name": "beta.txt", "metadata": {"tag": "alpha-tag"}},
            ]
        )
        result = h.search_blobs("c", "alpha", search_in_metadata=True)
        assert len(result) == 2

    def test_search_blobs_error(self, blob_service_mock):
        h = _make_helper(blob_service_mock)
        h.list_blobs = MagicMock(side_effect=RuntimeError("x"))
        with pytest.raises(RuntimeError):
            h.search_blobs("c", "alpha")
