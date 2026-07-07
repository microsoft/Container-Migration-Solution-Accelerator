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

# Load values from `azd env get-values` when any required value is missing. This
# covers not just the registry/resource group but also the container app names
# and registry endpoint, so a partially-populated environment does not silently
# skip image updates and leave apps on the placeholder image.
if ([string]::IsNullOrEmpty($AcrName) -or [string]::IsNullOrEmpty($ResourceGroup) -or [string]::IsNullOrEmpty($RegistryEndpoint) -or [string]::IsNullOrEmpty($BackendApp) -or [string]::IsNullOrEmpty($FrontendApp) -or [string]::IsNullOrEmpty($ProcessorApp)) {
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
        Write-Error "Container app name for '$ImageName' is not set; cannot update its image. Ensure the deployment outputs / azd environment include the container app names so the app is not left on the placeholder image."
        exit 1
    }
    Write-Host "==> Updating container app '$AppName' -> $RegistryEndpoint/${ImageName}:$ImageTag"
    az containerapp update `
        --name $AppName `
        --resource-group $ResourceGroup `
        --image "$RegistryEndpoint/${ImageName}:$ImageTag" `
        --output none
    if ($LASTEXITCODE -ne 0) { throw "az containerapp update failed for $AppName" }
}

# ---------------------------------------------------------------------------
# WAF (private networking) support.
#
# In WAF mode the registry has public network access DISABLED at rest (with a
# default-deny network rule set and image export disabled); runtime pulls flow
# over a private endpoint. Remote build (az acr build / ACR Tasks) reaches the
# registry over its PUBLIC endpoint, so we temporarily relax those settings for
# the build/push and restore them afterwards - including on failure, via finally
# - so the registry is never left publicly reachable. WAF is detected from the
# resource group's 'Type' tag (set to 'WAF' when private networking is enabled).
# ---------------------------------------------------------------------------
$DeploymentType = az group show --name $ResourceGroup --query 'tags.Type' -o tsv 2>$null
if ($DeploymentType -eq 'WAF') {
    Write-Host "==> WAF deployment detected - temporarily relaxing ACR restrictions for the image push"
    az acr update --name $AcrName --resource-group $ResourceGroup --allow-exports true --output none --only-show-errors
    if ($LASTEXITCODE -ne 0) { throw "Failed to enable ACR exports." }
    az acr update --name $AcrName --resource-group $ResourceGroup --public-network-enabled true --output none --only-show-errors
    if ($LASTEXITCODE -ne 0) { throw "Failed to enable ACR public network access." }
    az acr update --name $AcrName --resource-group $ResourceGroup --default-action Allow --output none --only-show-errors
    if ($LASTEXITCODE -ne 0) { throw "Failed to set ACR default action to Allow." }
    Write-Host "    Waiting ~45s for the network rule change to propagate..."
    Start-Sleep -Seconds 45
}

try {
    # Build & push all images to the dedicated ACR.
    Build-Image -ImageName 'backend-api' -ContextDir (Join-Path $RootDir 'src/backend-api')
    Build-Image -ImageName 'processor'   -ContextDir (Join-Path $RootDir 'src/processor')
    Build-Image -ImageName 'frontend'    -ContextDir (Join-Path $RootDir 'src/frontend')

    # Point the Container Apps at the freshly built images.
    Update-App -AppName $BackendApp   -ImageName 'backend-api'
    Update-App -AppName $ProcessorApp -ImageName 'processor'
    Update-App -AppName $FrontendApp  -ImageName 'frontend'
}
finally {
    if ($DeploymentType -eq 'WAF') {
        Write-Host "==> Restoring WAF ACR configuration (default-action Deny, public access disabled, exports off)"
        az acr update --name $AcrName --resource-group $ResourceGroup --default-action Deny --output none --only-show-errors
        az acr update --name $AcrName --resource-group $ResourceGroup --public-network-enabled false --output none --only-show-errors
        az acr update --name $AcrName --resource-group $ResourceGroup --allow-exports false --output none --only-show-errors
        if ($LASTEXITCODE -ne 0) { Write-Warning "Failed to fully restore ACR configuration; verify manually." }
    }
}

Write-Host "==> [deploy_container_images] Completed successfully."
