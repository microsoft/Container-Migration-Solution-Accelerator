# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from utils import security_policy_evidence as spe


def _blob(name, size=10):
    return SimpleNamespace(name=name, size=size)


def _container_with_blobs(name_to_text: dict, blobs):
    """Build a mock container client whose list_blobs returns `blobs` and whose
    get_blob_client(name) returns a blob client serving name_to_text[name]."""
    cc = MagicMock()
    cc.list_blobs.return_value = blobs

    def _get_blob_client(name):
        bc = MagicMock()
        text = name_to_text.get(name, "")
        bc.download_blob.return_value.readall.return_value = text.encode("utf-8")
        return bc

    cc.get_blob_client.side_effect = _get_blob_client
    return cc


@pytest.fixture
def patch_client():
    """Patch `_get_blob_service_client` so no real Azure call is made."""

    def _apply(container_client):
        client = MagicMock()
        client.get_container_client.return_value = container_client
        return patch.object(spe, "_get_blob_service_client", return_value=client)

    return _apply


class TestGetBlobServiceClient:
    def test_account_name_uses_credential(self, monkeypatch):
        monkeypatch.setenv("STORAGE_ACCOUNT_NAME", "myacct")
        with patch.object(spe, "BlobServiceClient") as bsc, patch.object(
            spe, "get_azure_credential", return_value="cred"
        ):
            bsc.return_value = "client"
            result = spe._get_blob_service_client()
            bsc.assert_called_once_with(
                account_url="https://myacct.blob.core.windows.net",
                credential="cred",
            )
            assert result == "client"

    def test_alt_account_env_used(self, monkeypatch):
        monkeypatch.delenv("STORAGE_ACCOUNT_NAME", raising=False)
        monkeypatch.setenv("AZURE_STORAGE_ACCOUNT_NAME", "alt")
        with patch.object(spe, "BlobServiceClient") as bsc, patch.object(
            spe, "get_azure_credential", return_value="c"
        ):
            spe._get_blob_service_client()
            assert "alt.blob.core.windows.net" in bsc.call_args.kwargs["account_url"]

    def test_connection_string_fallback(self, monkeypatch):
        monkeypatch.delenv("STORAGE_ACCOUNT_NAME", raising=False)
        monkeypatch.delenv("AZURE_STORAGE_ACCOUNT_NAME", raising=False)
        monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "DefaultEndpointsProtocol=https;...")
        with patch.object(spe, "BlobServiceClient") as bsc:
            bsc.from_connection_string.return_value = "from-cs"
            result = spe._get_blob_service_client()
            bsc.from_connection_string.assert_called_once()
            assert result == "from-cs"

    def test_missing_config_raises(self, monkeypatch):
        for key in [
            "STORAGE_ACCOUNT_NAME",
            "AZURE_STORAGE_ACCOUNT_NAME",
            "AZURE_STORAGE_CONNECTION_STRING",
            "STORAGE_CONNECTION_STRING",
            "AzureWebJobsStorage",
        ]:
            monkeypatch.delenv(key, raising=False)
        with pytest.raises(RuntimeError):
            spe._get_blob_service_client()


class TestCollectSecurityPolicyEvidence:
    def test_empty_folder_returns_zero_findings(self, patch_client):
        cc = _container_with_blobs({}, [])
        with patch_client(cc):
            result = spe.collect_security_policy_evidence(
                container_name="c", source_folder="proj/"
            )
        assert result["scanned_files"] == 0
        assert result["findings"] == []
        assert result["errors"] == []
        assert result["source_folder"] == "proj"

    def test_list_blobs_failure_surfaces_error(self, patch_client):
        cc = MagicMock()
        cc.list_blobs.side_effect = RuntimeError("listing blew up")
        with patch_client(cc):
            result = spe.collect_security_policy_evidence(
                container_name="c", source_folder="x"
            )
        assert result["findings"] == []
        assert any("list_blobs_failed" in e for e in result["errors"])

    def test_skips_non_relevant_extensions(self, patch_client):
        cc = _container_with_blobs(
            {"foo.png": "irrelevant"}, [_blob("foo.png")]
        )
        with patch_client(cc):
            result = spe.collect_security_policy_evidence(
                container_name="c", source_folder=""
            )
        assert result["scanned_files"] == 0

    def test_skips_keep_files(self, patch_client):
        cc = _container_with_blobs(
            {"folder/.keep": ""}, [_blob("folder/.keep")]
        )
        with patch_client(cc):
            result = spe.collect_security_policy_evidence(
                container_name="c", source_folder=""
            )
        assert result["scanned_files"] == 0

    def test_skips_oversized_files(self, patch_client):
        cc = _container_with_blobs(
            {"big.yaml": "x"}, [_blob("big.yaml", size=10_000_000)]
        )
        with patch_client(cc):
            result = spe.collect_security_policy_evidence(
                container_name="c",
                source_folder="",
                max_bytes_per_file=1024,
            )
        assert result["scanned_files"] == 0
        assert result["skipped_files"] == 1

    def test_max_files_cap_respected(self, patch_client):
        names = [f"f{i}.yaml" for i in range(5)]
        cc = _container_with_blobs({n: "no signals here" for n in names}, [_blob(n) for n in names])
        with patch_client(cc):
            result = spe.collect_security_policy_evidence(
                container_name="c", source_folder="", max_files=2
            )
        assert result["scanned_files"] == 2

    def test_detects_aws_pattern(self, patch_client):
        text = "key: AKIAIOSFODNN7EXAMPLE\n"
        cc = _container_with_blobs({"a.yaml": text}, [_blob("a.yaml")])
        with patch_client(cc):
            result = spe.collect_security_policy_evidence(
                container_name="c", source_folder=""
            )
        assert result["scanned_files"] == 1
        assert result["findings"][0]["signals"] == ["aws_access_key_id_pattern"]

    def test_detects_gcp_and_generic(self, patch_client):
        text = "private_key_id: abc\npassword: hunter2\n"
        cc = _container_with_blobs({"x.json": text}, [_blob("x.json")])
        with patch_client(cc):
            result = spe.collect_security_policy_evidence(
                container_name="c", source_folder=""
            )
        signals = result["findings"][0]["signals"]
        assert "gcp_service_account_key_fields" in signals
        assert "generic_secret_keywords" in signals

    def test_extracts_secret_key_names_from_k8s_secret(self, patch_client):
        text = (
            "apiVersion: v1\n"
            "kind: Secret\n"
            "metadata:\n"
            "  name: app\n"
            "data:\n"
            "  username: dXNlcg==\n"
            "  password: cGFzcw==\n"
            "type: Opaque\n"
        )
        cc = _container_with_blobs({"s.yaml": text}, [_blob("s.yaml")])
        with patch_client(cc):
            result = spe.collect_security_policy_evidence(
                container_name="c", source_folder=""
            )
        finding = result["findings"][0]
        assert "k8s_kind_secret" in finding["signals"]
        assert "username" in finding["secret_key_names"]
        assert "password" in finding["secret_key_names"]

    def test_per_file_download_error_recorded_and_continues(self, patch_client):
        good_text = "password: foo\n"
        cc = MagicMock()
        cc.list_blobs.return_value = [_blob("bad.yaml"), _blob("good.yaml")]

        def _get_blob_client(name):
            bc = MagicMock()
            if name == "bad.yaml":
                bc.download_blob.side_effect = RuntimeError("download failed")
            else:
                bc.download_blob.return_value.readall.return_value = good_text.encode()
            return bc

        cc.get_blob_client.side_effect = _get_blob_client
        with patch_client(cc):
            result = spe.collect_security_policy_evidence(
                container_name="c", source_folder=""
            )
        assert any("bad.yaml" in e for e in result["errors"])
        assert any(f["blob"] == "good.yaml" for f in result["findings"])

    def test_no_signals_no_finding(self, patch_client):
        cc = _container_with_blobs({"plain.txt": "nothing interesting"}, [_blob("plain.txt")])
        with patch_client(cc):
            result = spe.collect_security_policy_evidence(
                container_name="c", source_folder=""
            )
        assert result["scanned_files"] == 1
        assert result["findings"] == []
