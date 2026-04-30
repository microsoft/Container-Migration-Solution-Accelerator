# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Tests for utils.security_policy_evidence."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from utils import security_policy_evidence as spe


# ---------- _get_blob_service_client ----------


def test_get_blob_service_client_uses_account_name_and_credential(monkeypatch):
    monkeypatch.setenv("STORAGE_ACCOUNT_NAME", "acct")
    fake_cred = MagicMock(name="cred")
    fake_client = MagicMock(name="client")
    with (
        patch.object(spe, "get_azure_credential", return_value=fake_cred),
        patch.object(spe, "BlobServiceClient", return_value=fake_client) as bsc,
    ):
        out = spe._get_blob_service_client()
    assert out is fake_client
    bsc.assert_called_once_with(
        account_url="https://acct.blob.core.windows.net", credential=fake_cred
    )


def test_get_blob_service_client_falls_back_to_connection_string(monkeypatch):
    monkeypatch.delenv("STORAGE_ACCOUNT_NAME", raising=False)
    monkeypatch.delenv("AZURE_STORAGE_ACCOUNT_NAME", raising=False)
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", " conn-str ")
    fake_client = MagicMock()
    bsc_cls = MagicMock()
    bsc_cls.from_connection_string.return_value = fake_client
    with patch.object(spe, "BlobServiceClient", bsc_cls):
        out = spe._get_blob_service_client()
    assert out is fake_client
    bsc_cls.from_connection_string.assert_called_once_with("conn-str")


def test_get_blob_service_client_raises_when_unconfigured(monkeypatch):
    for v in [
        "STORAGE_ACCOUNT_NAME",
        "AZURE_STORAGE_ACCOUNT_NAME",
        "AZURE_STORAGE_CONNECTION_STRING",
        "STORAGE_CONNECTION_STRING",
        "AzureWebJobsStorage",
    ]:
        monkeypatch.delenv(v, raising=False)
    with pytest.raises(RuntimeError, match="Azure Storage not configured"):
        spe._get_blob_service_client()


# ---------- collect_security_policy_evidence ----------


def _make_blob(name, size=100):
    return SimpleNamespace(name=name, size=size)


def _container_with(blobs, blob_data: dict):
    """Build a fake container_client returning given blobs and blob bytes."""
    container = MagicMock()
    container.list_blobs.return_value = iter(blobs)

    def _get_blob_client(name):
        client = MagicMock()
        download = MagicMock()
        download.readall.return_value = blob_data.get(name, b"")
        client.download_blob.return_value = download
        return client

    container.get_blob_client.side_effect = _get_blob_client
    return container


def _patch_blob_service(container):
    bsc = MagicMock()
    bsc.get_container_client.return_value = container
    return patch.object(spe, "_get_blob_service_client", return_value=bsc)


def test_collect_skips_marker_files_and_unsupported_extensions():
    blobs = [
        _make_blob("foo/.keep"),
        _make_blob("foo/bar.KEEP"),
        _make_blob("foo/binary.png"),
    ]
    container = _container_with(blobs, {})
    with _patch_blob_service(container):
        result = spe.collect_security_policy_evidence(
            container_name="c", source_folder="/foo/"
        )
    assert result["scanned_files"] == 0
    assert result["findings"] == []
    assert result["source_folder"] == "foo"


def test_collect_skips_files_exceeding_size_limit():
    blobs = [_make_blob("foo/a.yaml", size=10_000)]
    container = _container_with(blobs, {})
    with _patch_blob_service(container):
        result = spe.collect_security_policy_evidence(
            container_name="c", source_folder="foo", max_bytes_per_file=100
        )
    assert result["scanned_files"] == 0
    assert result["skipped_files"] == 1


def test_collect_detects_secret_kind_and_extracts_keys():
    yaml_text = (
        b"apiVersion: v1\n"
        b"kind: Secret\n"
        b"metadata:\n"
        b"  name: my-secret\n"
        b"data:\n"
        b"  username: dXNlcg==\n"
        b"  password: cGFzcw==\n"
        b"\n"
        b"  api_key: a2V5\n"
        b"metadata2:\n"
        b"  unrelated: true\n"
    )
    blobs = [_make_blob("foo/secret.yaml", size=len(yaml_text))]
    container = _container_with(blobs, {"foo/secret.yaml": yaml_text})
    with _patch_blob_service(container):
        result = spe.collect_security_policy_evidence(
            container_name="c", source_folder="foo"
        )
    assert result["scanned_files"] == 1
    assert len(result["findings"]) == 1
    finding = result["findings"][0]
    assert finding["blob"] == "foo/secret.yaml"
    assert "k8s_kind_secret" in finding["signals"]
    assert "generic_secret_keywords" in finding["signals"]
    # Keys captured from the data block (in order of appearance, dedup)
    assert finding["secret_key_names"] == ["username", "password", "api_key"]


def test_collect_detects_aws_and_gcp_patterns():
    text = (
        b"some_access_key: AKIAABCDEFGHIJKLMNOP\n"
        b"private_key_id: foo\n"
    )
    blobs = [_make_blob("a.json", size=len(text))]
    container = _container_with(blobs, {"a.json": text})
    with _patch_blob_service(container):
        result = spe.collect_security_policy_evidence(
            container_name="c", source_folder=""
        )
    assert len(result["findings"]) == 1
    signals = result["findings"][0]["signals"]
    assert "aws_access_key_id_pattern" in signals
    assert "gcp_service_account_key_fields" in signals


def test_collect_no_signals_yields_no_findings():
    blobs = [_make_blob("benign.txt", size=10)]
    container = _container_with(blobs, {"benign.txt": b"hello world"})
    with _patch_blob_service(container):
        result = spe.collect_security_policy_evidence(
            container_name="c", source_folder=""
        )
    assert result["scanned_files"] == 1
    assert result["findings"] == []


def test_collect_records_error_and_continues_on_blob_download_failure():
    blobs = [
        _make_blob("a.yaml", size=10),
        _make_blob("b.yaml", size=10),
    ]
    container = MagicMock()
    container.list_blobs.return_value = iter(blobs)

    bad_client = MagicMock()
    bad_client.download_blob.side_effect = RuntimeError("download boom")

    good_client = MagicMock()
    good_dl = MagicMock()
    good_dl.readall.return_value = b"kind: Secret\n"
    good_client.download_blob.return_value = good_dl

    container.get_blob_client.side_effect = [bad_client, good_client]

    with _patch_blob_service(container):
        result = spe.collect_security_policy_evidence(
            container_name="c", source_folder=""
        )
    assert result["scanned_files"] == 2
    assert any("download boom" in e for e in result["errors"])
    # Second file produced a finding.
    assert len(result["findings"]) == 1
    assert result["findings"][0]["blob"] == "b.yaml"


def test_collect_returns_listing_error_envelope():
    container = MagicMock()
    container.list_blobs.side_effect = RuntimeError("list fail")
    with _patch_blob_service(container):
        result = spe.collect_security_policy_evidence(
            container_name="c", source_folder="x"
        )
    assert result["findings"] == []
    assert any("list_blobs_failed" in e for e in result["errors"])
    assert result["scanned_files"] == 0


def test_collect_respects_max_files_limit():
    blobs = [_make_blob(f"f{i}.yaml", size=10) for i in range(5)]
    payload = {b.name: b"hello" for b in blobs}
    container = _container_with(blobs, payload)
    with _patch_blob_service(container):
        result = spe.collect_security_policy_evidence(
            container_name="c", source_folder="", max_files=2
        )
    assert result["scanned_files"] == 2


def test_collect_caps_secret_key_names_at_25():
    keys = "\n".join(f"  k{i}: v{i}" for i in range(40))
    text = ("kind: Secret\nmetadata:\n  name: x\ndata:\n" + keys + "\n").encode()
    blobs = [_make_blob("big.yaml", size=len(text))]
    container = _container_with(blobs, {"big.yaml": text})
    with _patch_blob_service(container):
        result = spe.collect_security_policy_evidence(
            container_name="c", source_folder=""
        )
    assert len(result["findings"][0]["secret_key_names"]) == 25
