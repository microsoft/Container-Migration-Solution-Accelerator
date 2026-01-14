# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Security policy evidence collection (redacted).

This module performs a best-effort scan over a source artifact folder in Azure
Blob Storage to collect *non-sensitive* evidence when a security policy
violation is detected.

Key guarantee:
    Returned results never include secret values. Only blob names, key names,
    and high-level pattern signals are emitted for auditing/telemetry.
"""

import re
from typing import Any

from azure.storage.blob import BlobServiceClient

from utils.credential_util import get_azure_credential


def _get_blob_service_client() -> BlobServiceClient:
    """Create a BlobServiceClient using the same env conventions used elsewhere.

    Prefer account-name + Azure AD credential when available; fall back to connection string.
    """

    import os

    account_name = (
        os.getenv("STORAGE_ACCOUNT_NAME")
        or os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
        or ""
    ).strip()
    if account_name:
        account_url = f"https://{account_name}.blob.core.windows.net"
        credential = get_azure_credential()
        return BlobServiceClient(account_url=account_url, credential=credential)

    conn_str = (
        os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        or os.getenv("STORAGE_CONNECTION_STRING")
        or os.getenv("AzureWebJobsStorage")
    )
    if conn_str and conn_str.strip():
        return BlobServiceClient.from_connection_string(conn_str.strip())

    raise RuntimeError(
        "Azure Storage not configured. Set STORAGE_ACCOUNT_NAME (recommended) "
        "or AZURE_STORAGE_CONNECTION_STRING."
    )


_SECRET_KIND_RE = re.compile(r"(?im)^\s*kind\s*:\s*Secret\s*$")
_DATA_BLOCK_RE = re.compile(r"(?im)^\s*(data|stringData)\s*:\s*$")
_YAML_KEY_RE = re.compile(r"^\s*([A-Za-z0-9_.-]{1,128})\s*:\s*(.+)?\s*$")

_AWS_ACCESS_KEY_RE = re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")
_GCP_SA_KEY_ID_RE = re.compile(r"\bprivate_key_id\b")
_GENERIC_SECRET_WORD_RE = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|apikey|api_key|client_secret|access_key|private_key)\b"
)


def collect_security_policy_evidence(
    *,
    container_name: str,
    source_folder: str,
    max_files: int = 200,
    max_bytes_per_file: int = 512 * 1024,
) -> dict[str, Any]:
    """Best-effort scan to provide *redacted* evidence for SECURITY_POLICY_VIOLATION.

    Returns a JSON-serializable dict suitable for telemetry.
    Never returns secret values; only file names and key names/pattern matches.
    """

    prefix = (source_folder or "").strip().strip("/")
    client = _get_blob_service_client()
    container_client = client.get_container_client(container_name)

    findings: list[dict[str, Any]] = []
    scanned = 0
    skipped = 0
    errors: list[str] = []

    try:
        blobs = container_client.list_blobs(name_starts_with=prefix)
        for blob in blobs:
            if scanned >= max_files:
                break

            name = blob.name
            # Skip marker files / folders
            if (
                name.endswith("/.keep")
                or name.endswith("/.KEEP")
                or name.endswith(".KEEP")
            ):
                continue

            lower = name.lower()
            if not (
                lower.endswith(".yaml")
                or lower.endswith(".yml")
                or lower.endswith(".json")
                or lower.endswith(".env")
                or lower.endswith(".tfvars")
                or lower.endswith(".txt")
            ):
                continue

            size = int(getattr(blob, "size", 0) or 0)
            if size and size > max_bytes_per_file:
                skipped += 1
                continue

            scanned += 1
            try:
                blob_client = container_client.get_blob_client(name)
                raw = blob_client.download_blob().readall()
                text = raw.decode("utf-8", errors="replace")

                signals: list[str] = []
                secret_keys: list[str] = []

                if _SECRET_KIND_RE.search(text):
                    signals.append("k8s_kind_secret")

                    # Try to extract key names under data/stringData blocks (best-effort, regex-based)
                    lines = text.splitlines()
                    in_data = False
                    data_indent = None
                    for line in lines:
                        if _DATA_BLOCK_RE.match(line):
                            in_data = True
                            data_indent = len(line) - len(line.lstrip(" "))
                            continue

                        if in_data:
                            if not line.strip():
                                continue

                            indent = len(line) - len(line.lstrip(" "))
                            if data_indent is not None and indent <= data_indent:
                                in_data = False
                                data_indent = None
                                continue

                            m = _YAML_KEY_RE.match(line)
                            if m:
                                key = m.group(1)
                                if key and key not in secret_keys:
                                    secret_keys.append(key)
                                    if len(secret_keys) >= 25:
                                        break

                # Pattern-based hints (do not expose the matched value)
                if _AWS_ACCESS_KEY_RE.search(text):
                    signals.append("aws_access_key_id_pattern")
                if _GCP_SA_KEY_ID_RE.search(text):
                    signals.append("gcp_service_account_key_fields")
                if _GENERIC_SECRET_WORD_RE.search(text):
                    signals.append("generic_secret_keywords")

                if signals:
                    findings.append(
                        {
                            "blob": name,
                            "size_bytes": size,
                            "signals": sorted(set(signals)),
                            "secret_key_names": secret_keys,
                        }
                    )
            except Exception as e:
                errors.append(f"{name}: {type(e).__name__}: {e}")
                continue

    except Exception as e:
        # If listing itself fails, surface the error.
        return {
            "source_folder": prefix,
            "container": container_name,
            "scanned_files": scanned,
            "skipped_files": skipped,
            "findings": [],
            "errors": [f"list_blobs_failed: {type(e).__name__}: {e}"],
        }

    return {
        "source_folder": prefix,
        "container": container_name,
        "scanned_files": scanned,
        "skipped_files": skipped,
        "findings": findings,
        "errors": errors,
    }
