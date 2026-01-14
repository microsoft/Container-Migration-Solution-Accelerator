# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fastmcp>=2.12.5",
#   "httpx>=0.27.0,<1.0",
#   "azure-core>=1.36.0",
#   "azure-storage-blob>=12.27.1",
#   "azure-identity>=1.23.0",
#   "pyyaml>=6.0.2"
# ]
# ///

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import yaml
from azure.storage.blob import BlobServiceClient
from credential_util import get_azure_credential
from fastmcp import FastMCP

mcp = FastMCP(
    name="yaml_inventory_service",
    instructions=(
        "Generate a deterministic inventory of Kubernetes YAML resources from Azure Blob Storage. "
        "Use this to produce operator-grade runbooks without guessing namespaces/kinds/names."
    ),
)

_DEFAULT_CONTAINER = "default"
_blob_service_client: BlobServiceClient | None = None


def _get_blob_service_client() -> BlobServiceClient | None:
    global _blob_service_client

    if _blob_service_client is not None:
        return _blob_service_client

    account_name = os.getenv("STORAGE_ACCOUNT_NAME")
    if account_name:
        try:
            account_url = f"https://{account_name}.blob.core.windows.net"
            credential = get_azure_credential()
            _blob_service_client = BlobServiceClient(
                account_url=account_url, credential=credential
            )
            return _blob_service_client
        except Exception:
            return None

    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if connection_string:
        try:
            _blob_service_client = BlobServiceClient.from_connection_string(
                connection_string
            )
            return _blob_service_client
        except Exception:
            return None

    return None


def _normalize_folder_path(folder_path: str | None) -> str:
    if not folder_path:
        return ""
    folder_path = folder_path.strip().lstrip("/")
    return folder_path.rstrip("/")


def _full_blob_name(folder_path: str | None, blob_name: str) -> str:
    folder = _normalize_folder_path(folder_path)
    blob_name = blob_name.lstrip("/")
    if not folder:
        return blob_name
    return f"{folder}/{blob_name}"


def _iter_yaml_blobs(
    container_client,
    folder_path: str,
    recursive: bool,
) -> list[str]:
    prefix = _normalize_folder_path(folder_path)
    if prefix:
        prefix = prefix + "/"

    blob_names: list[str] = []
    for blob in container_client.list_blobs(name_starts_with=prefix):
        name = blob.name
        if not name:
            continue
        if not recursive:
            # Skip nested paths under the prefix
            remainder = (
                name[len(prefix) :] if prefix and name.startswith(prefix) else name
            )
            if "/" in remainder:
                continue

        lower = name.lower()
        if lower.endswith(".yaml") or lower.endswith(".yml"):
            blob_names.append(name)

    blob_names.sort()
    return blob_names


_CLUSTER_SCOPED_KINDS = {
    "Namespace",
    "Node",
    "PersistentVolume",
    "StorageClass",
    "CSIDriver",
    "CSINode",
    "VolumeAttachment",
    "CustomResourceDefinition",
    "MutatingWebhookConfiguration",
    "ValidatingWebhookConfiguration",
    "APIService",
    "ClusterRole",
    "ClusterRoleBinding",
    "PriorityClass",
    "RuntimeClass",
    "PodSecurityPolicy",
}


def _is_cluster_scoped(kind: str | None) -> bool:
    return bool(kind) and kind in _CLUSTER_SCOPED_KINDS


@dataclass(frozen=True)
class _DocInfo:
    index: int
    apiVersion: str | None
    kind: str | None
    name: str | None
    namespace: str | None
    cluster_scoped: bool


def _extract_doc_info(doc: Any, index: int) -> _DocInfo | None:
    if not isinstance(doc, dict):
        return None

    api_version = doc.get("apiVersion")
    kind = doc.get("kind")

    metadata = doc.get("metadata")
    name = None
    namespace = None

    if isinstance(metadata, dict):
        name = metadata.get("name")
        namespace = metadata.get("namespace")

    kind_str = str(kind) if kind is not None else None
    return _DocInfo(
        index=index,
        apiVersion=str(api_version) if api_version is not None else None,
        kind=kind_str,
        name=str(name) if name is not None else None,
        namespace=str(namespace) if namespace is not None else None,
        cluster_scoped=_is_cluster_scoped(kind_str),
    )


def _apply_group_for_kinds(kinds: set[str]) -> tuple[int, str, str]:
    # Lower index means earlier apply.
    # Keep this intentionally simple/deterministic.
    if "CustomResourceDefinition" in kinds or "APIService" in kinds:
        return (0, "00-foundation", "CRDs / APIService")
    if "Namespace" in kinds or "StorageClass" in kinds or "PersistentVolume" in kinds:
        return (0, "00-foundation", "Namespaces / Storage")

    if kinds.intersection(
        {"ServiceAccount", "Role", "RoleBinding", "ClusterRole", "ClusterRoleBinding"}
    ):
        return (10, "10-rbac", "RBAC")

    if kinds.intersection(
        {"ConfigMap", "Secret", "Service", "Endpoints", "EndpointSlice"}
    ):
        return (20, "20-core", "Config / Service")

    if kinds.intersection(
        {"Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob", "ReplicaSet"}
    ):
        return (30, "30-workloads", "Workloads")

    if kinds.intersection(
        {"Ingress", "IngressClass", "Gateway", "HTTPRoute", "GRPCRoute", "TLSRoute"}
    ):
        return (40, "40-ingress", "Ingress / Gateway")

    return (50, "50-misc", "Other resources")


@mcp.tool()
def generate_converted_yaml_inventory(
    container_name: str | None,
    folder_path: str,
    output_blob_name: str = "converted_yaml_inventory.json",
    output_folder_path: str | None = None,
    recursive: bool = True,
) -> str:
    """Generate an inventory JSON for YAML blobs under a given folder.

    Args:
        container_name: Azure blob container name (use None for default).
        folder_path: Blob folder path to scan (typically '<process_id>/output').
        output_blob_name: Output inventory blob filename.
        output_folder_path: Folder path for output blob (defaults to folder_path).
        recursive: Whether to scan recursively under folder_path.

    Returns:
        Human-readable status message. The inventory JSON is saved to blob storage.
    """

    if not isinstance(folder_path, str) or not folder_path.strip():
        return "[FAILED] folder_path must be a non-empty string"

    if container_name is None:
        container_name = _DEFAULT_CONTAINER

    if not isinstance(container_name, str) or not container_name.strip():
        return "[FAILED] container_name must be a non-empty string or None"

    client = _get_blob_service_client()
    if client is None:
        return (
            "[FAILED] Azure Blob client not configured. "
            "Set STORAGE_ACCOUNT_NAME (recommended) or AZURE_STORAGE_CONNECTION_STRING."
        )

    try:
        container_client = client.get_container_client(container_name)

        scan_folder = _normalize_folder_path(folder_path)
        out_folder = (
            _normalize_folder_path(output_folder_path)
            if output_folder_path
            else scan_folder
        )

        blob_names = _iter_yaml_blobs(container_client, scan_folder, recursive)
        if not blob_names:
            return (
                f"[FAILED] No YAML/YML blobs found under: {container_name}/{scan_folder} "
                f"(recursive={recursive})"
            )

        files: list[dict[str, Any]] = []
        warnings: list[str] = []

        for blob_name in blob_names:
            try:
                blob_client = container_client.get_blob_client(blob=blob_name)
                content_bytes = blob_client.download_blob().readall()
                sha256 = hashlib.sha256(content_bytes).hexdigest()
                content_text = content_bytes.decode("utf-8", errors="replace")

                docs: list[_DocInfo] = []
                parsed_docs = list(yaml.safe_load_all(content_text))
                for idx, doc in enumerate(parsed_docs):
                    if doc is None:
                        continue
                    info = _extract_doc_info(doc, idx)
                    if info is None:
                        warnings.append(
                            f"Non-mapping YAML doc ignored: {blob_name} (doc #{idx})"
                        )
                        continue

                    if info.kind is None or info.name is None:
                        warnings.append(f"Missing kind/name: {blob_name} (doc #{idx})")

                    docs.append(info)

                if not docs:
                    warnings.append(f"No Kubernetes docs parsed from: {blob_name}")

                files.append(
                    {
                        "path": blob_name,
                        "sha256": sha256,
                        "documents": [
                            {
                                "index": d.index,
                                "apiVersion": d.apiVersion,
                                "kind": d.kind,
                                "name": d.name,
                                "namespace": d.namespace,
                                "cluster_scoped": d.cluster_scoped,
                            }
                            for d in docs
                        ],
                    }
                )
            except Exception as e:
                warnings.append(f"Failed to process blob {blob_name}: {str(e)}")

        # Build apply groups by file
        groups_by_key: dict[tuple[int, str, str], list[str]] = {}
        for file_entry in files:
            kinds = {
                d.get("kind")
                for d in file_entry.get("documents", [])
                if isinstance(d, dict) and isinstance(d.get("kind"), str)
            }
            idx, name, rationale = _apply_group_for_kinds(set(kinds))
            groups_by_key.setdefault((idx, name, rationale), []).append(
                file_entry["path"]
            )

        apply_groups = []
        for (idx, name, rationale), paths in sorted(
            groups_by_key.items(), key=lambda x: x[0][0]
        ):
            apply_groups.append(
                {
                    "name": name,
                    "rationale": rationale,
                    "file_paths": sorted(paths),
                }
            )

        inventory = {
            "generated_at": datetime.now(UTC).isoformat(),
            "container": container_name,
            "scan_folder": scan_folder,
            "files": files,
            "apply_groups": apply_groups,
            "warnings": warnings,
        }

        payload = json.dumps(inventory, indent=2, ensure_ascii=False)

        out_blob_full_name = _full_blob_name(out_folder, output_blob_name)
        out_blob_client = container_client.get_blob_client(blob=out_blob_full_name)
        out_blob_client.upload_blob(payload.encode("utf-8"), overwrite=True)

        return (
            f"[SUCCESS] Generated converted YAML inventory\n"
            f"- Output: {container_name}/{out_blob_full_name}\n"
            f"- YAML blobs scanned: {len(blob_names)}\n"
            f"- Inventory entries: {len(files)}\n"
            f"- Warnings: {len(warnings)}"
        )

    except Exception as e:
        return f"[FAILED] Inventory generation failed: {str(e)}"


if __name__ == "__main__":
    mcp.run()
