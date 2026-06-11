// ============================================================================
// main_custom.bicep — Deployment Router (Custom Image Variant)
// Description: Routes deployment to the appropriate infrastructure flavor.
//   Same as main.bicep but accepts per-service container image names
//   (backendImageName, processorImageName, frontendImageName) instead of
//   registry endpoint + tag.
//   - 'bicep'   → Vanilla Bicep modules (Docker deployment)
//   - 'avm'     → AVM-based modules (non-WAF)
//   - 'avm-waf' → AVM-based modules with WAF-aligned features
// ============================================================================
targetScope = 'resourceGroup'

// ============================================================================
// Routing Parameter
// ============================================================================

@allowed(['bicep', 'avm', 'avm-waf'])
@description('Required. Deployment flavor: bicep (vanilla Docker), avm (AVM non-WAF), or avm-waf (AVM WAF-aligned).')
param deploymentFlavor string

// ============================================================================
// Parameters — Core
// ============================================================================

@minLength(3)
@maxLength(16)
@description('Required. A unique application/solution name for all resources in this deployment.')
param solutionName string = 'containermig'

@maxLength(5)
@description('Optional. A unique text suffix appended to resource names for uniqueness.')
param solutionUniqueText string = substring(uniqueString(subscription().id, resourceGroup().name, solutionName), 0, 5)

@description('Optional. Primary Azure region for resource deployment. Defaults to resource group location.')
param location string = ''

@allowed([
  'australiaeast'
  'eastus'
  'eastus2'
  'francecentral'
  'japaneast'
  'norwayeast'
  'southindia'
  'swedencentral'
  'uksouth'
  'westus'
  'westus3'
])
@metadata({
  azd: {
    type: 'location'
    usageName: [
      'OpenAI.GlobalStandard.gpt-5.1,500'
    ]
  }
})
@description('Required. Azure region for AI services (OpenAI/AI Foundry).')
param azureAiServiceLocation string

@description('Optional. Secondary location for Cosmos DB resources.')
param cosmosLocation string = 'eastus2'

// ============================================================================
// Parameters — AI Configuration
// ============================================================================

@allowed(['Standard', 'GlobalStandard'])
@description('Optional. GPT model deployment type.')
param deploymentType string = 'GlobalStandard'

@description('Optional. Name of the GPT model to deploy.')
param gptModelName string = 'gpt-5.1'

@description('Optional. Version of the GPT model.')
param gptModelVersion string = '2025-11-13'

@description('Optional. GPT model deployment capacity.')
param gptDeploymentCapacity int = 500

@description('Optional. Name of the embedding model to deploy.')
param embeddingModel string = 'text-embedding-3-large'

@description('Optional. Version of the embedding model.')
param embeddingModelVersion string = '1'

@allowed(['Standard', 'GlobalStandard'])
@description('Optional. Embedding model deployment type.')
param embeddingDeploymentType string = 'GlobalStandard'

@description('Optional. Embedding model deployment capacity.')
param embeddingDeploymentCapacity int = 500

// ============================================================================
// Parameters — Container Images (custom variant)
// ============================================================================

@description('Optional. Full container image name for the backend API service.')
param backendImageName string = ''

@description('Optional. Full container image name for the processor service.')
param processorImageName string = ''

@description('Optional. Full container image name for the frontend service.')
param frontendImageName string = ''

// ============================================================================
// Parameters — Existing Resources
// ============================================================================

@description('Optional. Resource ID of an existing Foundry project.')
param existingFoundryProjectResourceId string = ''

@description('Optional. Existing Log Analytics Workspace Resource ID.')
param existingLogAnalyticsWorkspaceId string = ''

// ============================================================================
// Parameters — Tags & Telemetry
// ============================================================================

@description('Optional. Tags to apply to all resources.')
param tags object = {}

// ============================================================================
// Derived Variables
// ============================================================================

var isAvm = deploymentFlavor == 'avm' || deploymentFlavor == 'avm-waf'
var isBicep = deploymentFlavor == 'bicep'

// ============================================================================
// Module: Vanilla Bicep Deployment (Custom Images)
// ============================================================================

module bicepDeployment './bicep/main_custom.bicep' = if (isBicep) {
  name: take('module.bicep-custom.${solutionName}', 64)
  params: {
    solutionName: solutionName
    solutionUniqueText: solutionUniqueText
    location: location
    tags: tags
    azureAiServiceLocation: azureAiServiceLocation
    cosmosLocation: cosmosLocation
    deploymentType: deploymentType
    gptModelName: gptModelName
    gptModelVersion: gptModelVersion
    gptDeploymentCapacity: gptDeploymentCapacity
    embeddingModel: embeddingModel
    embeddingModelVersion: embeddingModelVersion
    embeddingDeploymentType: embeddingDeploymentType
    embeddingDeploymentCapacity: embeddingDeploymentCapacity
    backendImageName: backendImageName
    processorImageName: processorImageName
    frontendImageName: frontendImageName
    existingFoundryProjectResourceId: existingFoundryProjectResourceId
    existingLogAnalyticsWorkspaceId: existingLogAnalyticsWorkspaceId
  }
}

// ============================================================================
// Module: AVM Deployment (Custom Images)
// Note: AVM main_custom.bicep not yet implemented; routes to bicep for now.
// ============================================================================

module avmDeployment './bicep/main_custom.bicep' = if (isAvm) {
  name: take('module.avm-custom.${solutionName}', 64)
  params: {
    solutionName: solutionName
    solutionUniqueText: solutionUniqueText
    location: location
    tags: tags
    azureAiServiceLocation: azureAiServiceLocation
    cosmosLocation: cosmosLocation
    deploymentType: deploymentType
    gptModelName: gptModelName
    gptModelVersion: gptModelVersion
    gptDeploymentCapacity: gptDeploymentCapacity
    embeddingModel: embeddingModel
    embeddingModelVersion: embeddingModelVersion
    embeddingDeploymentType: embeddingDeploymentType
    embeddingDeploymentCapacity: embeddingDeploymentCapacity
    backendImageName: backendImageName
    processorImageName: processorImageName
    frontendImageName: frontendImageName
    existingFoundryProjectResourceId: existingFoundryProjectResourceId
    existingLogAnalyticsWorkspaceId: existingLogAnalyticsWorkspaceId
  }
}

// ============================================================================
// Outputs — Coalesced from whichever flavor was deployed
// ============================================================================

@description('Name of the deployed resource group.')
output resourceGroupName string = resourceGroup().name

@description('The name of the frontend container app.')
output CONTAINER_FRONTEND_APP_NAME string = isBicep ? bicepDeployment!.outputs.CONTAINER_FRONTEND_APP_NAME : avmDeployment!.outputs.CONTAINER_FRONTEND_APP_NAME

@description('The FQDN of the frontend container app.')
output CONTAINER_FRONTEND_APP_FQDN string = isBicep ? bicepDeployment!.outputs.CONTAINER_FRONTEND_APP_FQDN : avmDeployment!.outputs.CONTAINER_FRONTEND_APP_FQDN

@description('The name of the web app container app.')
output CONTAINER_WEB_APP_NAME string = isBicep ? bicepDeployment!.outputs.CONTAINER_WEB_APP_NAME : avmDeployment!.outputs.CONTAINER_WEB_APP_NAME

@description('The FQDN of the web app container app.')
output CONTAINER_WEB_APP_FQDN string = isBicep ? bicepDeployment!.outputs.CONTAINER_WEB_APP_FQDN : avmDeployment!.outputs.CONTAINER_WEB_APP_FQDN

@description('The name of the API container app.')
output CONTAINER_API_APP_NAME string = isBicep ? bicepDeployment!.outputs.CONTAINER_API_APP_NAME : avmDeployment!.outputs.CONTAINER_API_APP_NAME

@description('The FQDN of the API container app.')
output CONTAINER_API_APP_FQDN string = isBicep ? bicepDeployment!.outputs.CONTAINER_API_APP_FQDN : avmDeployment!.outputs.CONTAINER_API_APP_FQDN

@description('The Azure subscription ID.')
output AZURE_SUBSCRIPTION_ID string = isBicep ? bicepDeployment!.outputs.AZURE_SUBSCRIPTION_ID : avmDeployment!.outputs.AZURE_SUBSCRIPTION_ID

@description('The Azure resource group name.')
output AZURE_RESOURCE_GROUP string = isBicep ? bicepDeployment!.outputs.AZURE_RESOURCE_GROUP : avmDeployment!.outputs.AZURE_RESOURCE_GROUP

@description('Backend service name for azd.')
output SERVICE_BACKEND_NAME string = isBicep ? bicepDeployment!.outputs.SERVICE_BACKEND_NAME : avmDeployment!.outputs.SERVICE_BACKEND_NAME

@description('Backend service URI for azd.')
output SERVICE_BACKEND_URI string = isBicep ? bicepDeployment!.outputs.SERVICE_BACKEND_URI : avmDeployment!.outputs.SERVICE_BACKEND_URI

@description('Processor service name for azd.')
output SERVICE_PROCESSOR_NAME string = isBicep ? bicepDeployment!.outputs.SERVICE_PROCESSOR_NAME : avmDeployment!.outputs.SERVICE_PROCESSOR_NAME

@description('Frontend service name for azd.')
output SERVICE_FRONTEND_NAME string = isBicep ? bicepDeployment!.outputs.SERVICE_FRONTEND_NAME : avmDeployment!.outputs.SERVICE_FRONTEND_NAME

@description('Frontend service URI for azd.')
output SERVICE_FRONTEND_URI string = isBicep ? bicepDeployment!.outputs.SERVICE_FRONTEND_URI : avmDeployment!.outputs.SERVICE_FRONTEND_URI
