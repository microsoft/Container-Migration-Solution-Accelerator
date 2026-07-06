<#
.SYNOPSIS
    Separate post-deployment script (Windows / PowerShell) that runs FIRST,
    before any existing post-deployment scripts.

.DESCRIPTION
    Builds the deployment-specific container images using Azure Container
    Registry *remote* builds (az acr build - no local Docker required) and
    pushes them to the dedicated, per-deployment ACR. It then updates the
    Container Apps to use the freshly pushed images.

    This does NOT depend on a shared/public registry or anonymous pull. Image
    pulls at runtime use identity-based authentication (the app's managed
    identity has the AcrPull role on the dedicated ACR).
#>

$ErrorActionPreference = 'Stop'

Write-Host "==> [deploy_container_images] Building and pushing images to the dedicated ACR (remote build)"

# ---------------------------------------------------------------------------
# Resolve required values. azd exports deployment outputs as environment
# variables inside hooks; fall back to `azd env get-values` if needed.
# ---------------------------------------------------------------------------
$AcrName          = $env:AZURE_CONTAINER_REGISTRY_NAME
$RegistryEndpoint = $env:AZURE_CONTAINER_REGISTRY_ENDPOINT
$ResourceGroup    = $env:AZURE_RESOURCE_GROUP
$ImageTag         = if ($env:AZURE_ENV_IMAGE_TAG) { $env:AZURE_ENV_IMAGE_TAG } else { 'latest_v2' }
$BackendApp       = $env:CONTAINER_API_APP_NAME
$FrontendApp      = $env:CONTAINER_WEB_APP_NAME
$ProcessorApp     = $env:CONTAINER_PROCESSOR_APP_NAME

if ([string]::IsNullOrEmpty($AcrName) -or [string]::IsNullOrEmpty($ResourceGroup)) {
    if (Get-Command azd -ErrorAction SilentlyContinue) {
        Write-Host "==> Loading missing values from 'azd env get-values'"
        foreach ($line in (azd env get-values)) {
            if ($line -match '^(?<k>[A-Za-z0-9_]+)="?(?<v>.*?)"?$') {
                $k = $Matches['k']; $v = $Matches['v']
                switch ($k) {
                    'AZURE_CONTAINER_REGISTRY_NAME'     { if (-not $AcrName)          { $AcrName = $v } }
                    'AZURE_CONTAINER_REGISTRY_ENDPOINT' { if (-not $RegistryEndpoint) { $RegistryEndpoint = $v } }
                    'AZURE_RESOURCE_GROUP'              { if (-not $ResourceGroup)    { $ResourceGroup = $v } }
                    'AZURE_ENV_IMAGE_TAG'               { if (-not $env:AZURE_ENV_IMAGE_TAG) { $ImageTag = $v } }
                    'CONTAINER_API_APP_NAME'            { if (-not $BackendApp)       { $BackendApp = $v } }
                    'CONTAINER_WEB_APP_NAME'            { if (-not $FrontendApp)      { $FrontendApp = $v } }
                    'CONTAINER_PROCESSOR_APP_NAME'      { if (-not $ProcessorApp)     { $ProcessorApp = $v } }
                }
            }
        }
    }
}

# Derive the login server from the registry name if it was not provided.
if ([string]::IsNullOrEmpty($RegistryEndpoint)) {
    $RegistryEndpoint = "$AcrName.azurecr.io"
}

$missing = @()
if ([string]::IsNullOrEmpty($AcrName))       { $missing += 'AZURE_CONTAINER_REGISTRY_NAME' }
if ([string]::IsNullOrEmpty($ResourceGroup)) { $missing += 'AZURE_RESOURCE_GROUP' }
if ($missing.Count -gt 0) {
    Write-Error "Missing required deployment values: $($missing -join ', '). Ensure infrastructure has been provisioned (azd provision) first."
    exit 1
}

# Ensure the Azure CLI is installed before any `az` invocation, so a missing
# CLI produces a clear, actionable error instead of an opaque failure in the
# azd hook logs.
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Error "Azure CLI ('az') is not installed or not on PATH. Install it from https://learn.microsoft.com/cli/azure/install-azure-cli and re-run."
    exit 1
}

# Ensure the Azure CLI has a valid, non-expired login. `az acr build` and
# `az containerapp update` authenticate via the az CLI (separate from azd), so a
# stale/expired token here would otherwise fail part-way through the build.
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Error "Azure CLI (az) is not installed or not on PATH. Install Azure CLI and re-run this script."
    exit 1
}

az account show --output none 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Azure CLI is not authenticated or its token has expired. Run 'az login' (add '--tenant <tenant-id>' if needed) and re-run this script."
    exit 1
}

# Resolve the repository root (this script lives in <root>/scripts).
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir   = Split-Path -Parent $ScriptDir

Write-Host "    Registry        : $RegistryEndpoint ($AcrName)"
Write-Host "    Resource group  : $ResourceGroup"
Write-Host "    Image tag       : $ImageTag"

function Build-Image {
    param([string]$ImageName, [string]$ContextDir)
    Write-Host "==> Remote build (az acr build): ${ImageName}:$ImageTag"
    az acr build `
        --registry $AcrName `
        --image "${ImageName}:$ImageTag" `
        --file (Join-Path $ContextDir 'Dockerfile') `
        $ContextDir
    if ($LASTEXITCODE -ne 0) { throw "az acr build failed for $ImageName" }
}

function Update-App {
    param([string]$AppName, [string]$ImageName)
    if ([string]::IsNullOrEmpty($AppName)) {
        Write-Host "WARN: Container app name for '$ImageName' not set; skipping image update."
        return
    }
    Write-Host "==> Updating container app '$AppName' -> $RegistryEndpoint/${ImageName}:$ImageTag"
    az containerapp update `
        --name $AppName `
        --resource-group $ResourceGroup `
        --image "$RegistryEndpoint/${ImageName}:$ImageTag" `
        --output none
    if ($LASTEXITCODE -ne 0) { throw "az containerapp update failed for $AppName" }
}

# Build & push all images to the dedicated ACR.
Build-Image -ImageName 'backend-api' -ContextDir (Join-Path $RootDir 'src/backend-api')
Build-Image -ImageName 'processor'   -ContextDir (Join-Path $RootDir 'src/processor')
Build-Image -ImageName 'frontend'    -ContextDir (Join-Path $RootDir 'src/frontend')

# Point the Container Apps at the freshly built images.
Update-App -AppName $BackendApp   -ImageName 'backend-api'
Update-App -AppName $ProcessorApp -ImageName 'processor'
Update-App -AppName $FrontendApp  -ImageName 'frontend'

Write-Host "==> [deploy_container_images] Completed successfully."
