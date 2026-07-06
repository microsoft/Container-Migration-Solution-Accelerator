#!/usr/bin/env bash
#
# deploy_container_images.sh
#
# Separate post-deployment script that runs FIRST (before any existing
# post-deployment scripts). It builds the deployment-specific container images
# using Azure Container Registry *remote* builds (az acr build - no local Docker
# required) and pushes them to the dedicated, per-deployment ACR. It then updates
# the Container Apps to use the freshly pushed images.
#
# This intentionally does NOT depend on a shared/public registry or anonymous
# pull. Image pulls at runtime use identity-based authentication (the app's
# managed identity has the AcrPull role on the dedicated ACR).
#
set -euo pipefail

echo "==> [deploy_container_images] Building and pushing images to the dedicated ACR (remote build)"

# ---------------------------------------------------------------------------
# Resolve required values. azd exports deployment outputs as environment
# variables inside hooks; fall back to `azd env get-values` if needed.
# ---------------------------------------------------------------------------
ACR_NAME="${AZURE_CONTAINER_REGISTRY_NAME:-}"
REGISTRY_ENDPOINT="${AZURE_CONTAINER_REGISTRY_ENDPOINT:-}"
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-}"
IMAGE_TAG="${AZURE_ENV_IMAGE_TAG:-latest_v2}"
BACKEND_APP="${CONTAINER_API_APP_NAME:-}"
FRONTEND_APP="${CONTAINER_WEB_APP_NAME:-}"
PROCESSOR_APP="${CONTAINER_PROCESSOR_APP_NAME:-}"

if [[ -z "$ACR_NAME" || -z "$RESOURCE_GROUP" ]]; then
  if command -v azd >/dev/null 2>&1; then
    echo "==> Loading missing values from 'azd env get-values'"
    while IFS='=' read -r key value; do
      value="${value%\"}"; value="${value#\"}"
      case "$key" in
        AZURE_CONTAINER_REGISTRY_NAME)     ACR_NAME="${ACR_NAME:-$value}" ;;
        AZURE_CONTAINER_REGISTRY_ENDPOINT) REGISTRY_ENDPOINT="${REGISTRY_ENDPOINT:-$value}" ;;
        AZURE_RESOURCE_GROUP)              RESOURCE_GROUP="${RESOURCE_GROUP:-$value}" ;;
        AZURE_ENV_IMAGE_TAG)               IMAGE_TAG="${IMAGE_TAG:-$value}" ;;
        CONTAINER_API_APP_NAME)            BACKEND_APP="${BACKEND_APP:-$value}" ;;
        CONTAINER_WEB_APP_NAME)            FRONTEND_APP="${FRONTEND_APP:-$value}" ;;
        CONTAINER_PROCESSOR_APP_NAME)      PROCESSOR_APP="${PROCESSOR_APP:-$value}" ;;
      esac
    done < <(azd env get-values 2>/dev/null || true)
  fi
fi

# Derive the login server from the registry name if it was not provided.
REGISTRY_ENDPOINT="${REGISTRY_ENDPOINT:-${ACR_NAME}.azurecr.io}"

missing=()
[[ -z "$ACR_NAME" ]]       && missing+=("AZURE_CONTAINER_REGISTRY_NAME")
[[ -z "$RESOURCE_GROUP" ]] && missing+=("AZURE_RESOURCE_GROUP")
if [[ ${#missing[@]} -gt 0 ]]; then
  echo "ERROR: Missing required deployment values: ${missing[*]}" >&2
  echo "       Ensure infrastructure has been provisioned (azd provision) first." >&2
  exit 1
fi

# Ensure the Azure CLI is installed before any `az` invocation. Under `set -e`
# a missing `az` would otherwise fail with an opaque "command not found" that is
# hard to diagnose in CI/azd hook logs.
if ! command -v az >/dev/null 2>&1; then
  echo "ERROR: Azure CLI ('az') is not installed or not on PATH." >&2
  echo "       Install it from https://learn.microsoft.com/cli/azure/install-azure-cli and re-run." >&2
  exit 1
fi

# Ensure the Azure CLI has a valid, non-expired login. `az acr build` and
# `az containerapp update` authenticate via the az CLI (separate from azd), so a
# stale/expired token here would otherwise fail part-way through the build.
if ! command -v az >/dev/null 2>&1; then
  echo "ERROR: Azure CLI (az) is not installed or not on PATH." >&2
  exit 1
fi
if ! az account show >/dev/null 2>&1; then
  echo "ERROR: Azure CLI is not authenticated or its token has expired." >&2
  echo "       Run 'az login' (add '--tenant <tenant-id>' if needed) and re-run this script." >&2
  exit 1
fi

# Resolve the repository root (this script lives in <root>/scripts).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "    Registry        : $REGISTRY_ENDPOINT ($ACR_NAME)"
echo "    Resource group  : $RESOURCE_GROUP"
echo "    Image tag       : $IMAGE_TAG"

# ---------------------------------------------------------------------------
# Remote build helper - uses ACR Tasks (az acr build) so no local Docker daemon
# is required on the machine running the deployment.
# ---------------------------------------------------------------------------
build_image() {
  local image_name="$1"
  local context_dir="$2"
  echo "==> Remote build (az acr build): ${image_name}:${IMAGE_TAG}"
  az acr build \
    --registry "$ACR_NAME" \
    --image "${image_name}:${IMAGE_TAG}" \
    --file "${context_dir}/Dockerfile" \
    "$context_dir"
}

update_app() {
  local app_name="$1"
  local image_name="$2"
  if [[ -z "$app_name" ]]; then
    echo "WARN: Container app name for '${image_name}' not set; skipping image update."
    return
  fi
  echo "==> Updating container app '${app_name}' -> ${REGISTRY_ENDPOINT}/${image_name}:${IMAGE_TAG}"
  az containerapp update \
    --name "$app_name" \
    --resource-group "$RESOURCE_GROUP" \
    --image "${REGISTRY_ENDPOINT}/${image_name}:${IMAGE_TAG}" \
    --output none
}

# Build & push all images to the dedicated ACR.
build_image "backend-api" "${ROOT_DIR}/src/backend-api"
build_image "processor"   "${ROOT_DIR}/src/processor"
build_image "frontend"    "${ROOT_DIR}/src/frontend"

# Point the Container Apps at the freshly built images.
update_app "$BACKEND_APP"   "backend-api"
update_app "$PROCESSOR_APP" "processor"
update_app "$FRONTEND_APP"  "frontend"

echo "==> [deploy_container_images] Completed successfully."
