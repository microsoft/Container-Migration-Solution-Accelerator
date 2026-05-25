# =============================================================
# LLM Token Usage Workbook Deployment Script
# =============================================================
# Usage:
#   .\deploy-workbooks.ps1 -ResourceGroup <rg-name> -AppInsightsResourceId <full-resource-id> [-Location <location>]
#
# Example:
#   .\deploy-workbooks.ps1 `
#     -ResourceGroup "rg-my-permanent-rg" `
#     -AppInsightsResourceId "/subscriptions/<sub>/resourcegroups/<rg>/providers/microsoft.insights/components/<name>" `
#     -Location "australiaeast"
# =============================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup,
    
    [Parameter(Mandatory=$true)]
    [string]$AppInsightsResourceId,
    
    [string]$Location = "australiaeast"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Deploy GKE workbook
$gkeContent = Get-Content "$scriptDir\workbook-gke-content.json" -Raw
$gkeId = [guid]::NewGuid().ToString()

$body = @{
    location = $Location
    kind = "shared"
    properties = @{
        displayName = "LLM Token Usage Dashboard - GKE"
        serializedData = $gkeContent
        version = "Notebook/1.0"
        sourceId = $AppInsightsResourceId
        category = "workbook"
    }
    tags = @{
        "hidden-title" = "LLM Token Usage Dashboard - GKE"
    }
} | ConvertTo-Json -Depth 5

$bodyFile = [System.IO.Path]::GetTempFileName()
$body | Set-Content $bodyFile -Encoding UTF8

az rest --method PUT `
    --url "https://management.azure.com/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$ResourceGroup/providers/microsoft.insights/workbooks/$($gkeId)?api-version=2022-04-01" `
    --body "@$bodyFile" `
    --headers "Content-Type=application/json" 2>&1 | Out-Null

Write-Host "Deployed GKE workbook: $gkeId"
Remove-Item $bodyFile

# Deploy EKS workbook
$eksContent = Get-Content "$scriptDir\workbook-eks-content.json" -Raw
$eksId = [guid]::NewGuid().ToString()

$body = @{
    location = $Location
    kind = "shared"
    properties = @{
        displayName = "LLM Token Usage Dashboard - EKS"
        serializedData = $eksContent
        version = "Notebook/1.0"
        sourceId = $AppInsightsResourceId
        category = "workbook"
    }
    tags = @{
        "hidden-title" = "LLM Token Usage Dashboard - EKS"
    }
} | ConvertTo-Json -Depth 5

$bodyFile = [System.IO.Path]::GetTempFileName()
$body | Set-Content $bodyFile -Encoding UTF8

az rest --method PUT `
    --url "https://management.azure.com/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$ResourceGroup/providers/microsoft.insights/workbooks/$($eksId)?api-version=2022-04-01" `
    --body "@$bodyFile" `
    --headers "Content-Type=application/json" 2>&1 | Out-Null

Write-Host "Deployed EKS workbook: $eksId"
Remove-Item $bodyFile

Write-Host "`nDone! Both workbooks deployed to $ResourceGroup"
