# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fastmcp>=2.12.5",
#   "azure-identity>=1.23.0"
# ]
# ///

import logging
import os

from azure.identity import (
    AzureCliCredential,
    AzureDeveloperCliCredential,
    DefaultAzureCredential,
    ManagedIdentityCredential,
)


def get_azure_credential():
    """Return an Azure credential appropriate for the current environment."""

    azure_env_indicators = [
        "WEBSITE_SITE_NAME",
        "AZURE_CLIENT_ID",
        "MSI_ENDPOINT",
        "IDENTITY_ENDPOINT",
        "KUBERNETES_SERVICE_HOST",
        "CONTAINER_REGISTRY_LOGIN",
    ]

    if any(os.getenv(indicator) for indicator in azure_env_indicators):
        logging.info(
            "[AUTH] Detected Azure environment - using ManagedIdentityCredential"
        )
        client_id = os.getenv("AZURE_CLIENT_ID")
        if client_id:
            return ManagedIdentityCredential(client_id=client_id)
        return ManagedIdentityCredential()

    credential_attempts: list[tuple[str, object]] = []

    try:
        logging.info(
            "[AUTH] Local development - trying AzureDeveloperCliCredential (azd auth login)"
        )
        credential_attempts.append(
            ("AzureDeveloperCliCredential", AzureDeveloperCliCredential())
        )
    except Exception as e:
        logging.warning(f"[AUTH] AzureDeveloperCliCredential failed: {e}")

    try:
        logging.info("[AUTH] Trying AzureCliCredential (az login)")
        credential_attempts.append(("AzureCliCredential", AzureCliCredential()))
    except Exception as e:
        logging.warning(f"[AUTH] AzureCliCredential failed: {e}")

    if credential_attempts:
        name, credential = credential_attempts[0]
        logging.info(f"[AUTH] Using {name} for local development")
        return credential

    logging.info("[AUTH] Falling back to DefaultAzureCredential")
    return DefaultAzureCredential()
