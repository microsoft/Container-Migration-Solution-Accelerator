// ============================================================================
// main.bicep — Deployment Router
// Description: Routes deployment to the appropriate infrastructure flavor.
//   - 'bicep'   → Vanilla Bicep modules (Docker deployment)
//   - 'avm'     → AVM-based modules (non-WAF)
//   - 'avm-waf' → AVM-based modules with WAF-aligned features
//              (monitoring, private networking, scalability, redundancy)
// ============================================================================
targetScope = 'resourceGroup'

// ============================================================================
// Routing Parameter
// ============================================================================

@allowed(['bicep', 'avm', 'avm-waf'])
@description('Required. Deployment flavor: bicep (vanilla Docker), avm (AVM non-WAF), or avm-waf (AVM WAF-aligned).')
param deploymentFlavor string

// ============================================================================
// Parameters — Core (shared across all flavors)
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
@description('Required. Azure region for AI services (OpenAI/AI Foundry). Must be a region that supports gpt-5.1 model deployment.')
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

@description('Optional. GPT model deployment capacity (tokens per minute in thousands).')
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
// Parameters — Compute
// ============================================================================

@description('Optional. The endpoint (excluding https://) of an existing container registry.')
param containerRegistryEndpoint string = 'containermigrationacr.azurecr.io'

@description('Optional. The image tag to use for container images.')
param imageTag string = 'latest_v2'

// ============================================================================
// Parameters — Existing Resources
// ============================================================================

@description('Optional. Resource ID of an existing Foundry project. Empty creates a new one.')
param existingFoundryProjectResourceId string = ''

@description('Optional. Existing Log Analytics Workspace Resource ID. Empty creates a new one.')
param existingLogAnalyticsWorkspaceId string = ''

// ============================================================================
// Parameters — Tags & Telemetry
// ============================================================================

@description('Optional. Tags to apply to all resources.')
param tags object = {}

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

// ============================================================================
// Parameters — AVM-specific (ignored when deploymentFlavor = 'bicep')
// ============================================================================

@description('Optional. Enable monitoring (Log Analytics, diagnostic settings). AVM flavors only.')
param enableMonitoring bool = false

@description('Optional. Enable private networking (VNet, private endpoints). AVM flavors only.')
param enablePrivateNetworking bool = false

@secure()
@description('Optional. VM admin username (AVM-WAF only, when private networking is enabled).')
param vmAdminUsername string?

@secure()
@description('Optional. VM admin password (AVM-WAF only, when private networking is enabled).')
param vmAdminPassword string?

@description('Optional. VM size for jumpbox (AVM-WAF only). Defaults to Standard_D2s_v5.')
param vmSize string = 'Standard_D2s_v5'

// ============================================================================
// Derived Variables
// ============================================================================

var isAvm = deploymentFlavor == 'avm' || deploymentFlavor == 'avm-waf'
var isBicep = deploymentFlavor == 'bicep'

// ============================================================================
// Module: AVM Deployment (non-WAF and WAF)
// Activated when deploymentFlavor = 'avm' or 'avm-waf'
// WAF features (monitoring, private networking) are enabled automatically
// for 'avm-waf'.
// ============================================================================

module avmDeployment './avm/main.bicep' = if (isAvm) {
  name: take('module.avm.${solutionName}', 64)
  params: {
    solutionName: solutionName
    solutionUniqueText: solutionUniqueText
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    enableMonitoring: enableMonitoring
    enablePrivateNetworking: enablePrivateNetworking
    vmAdminUsername: vmAdminUsername
    vmAdminPassword: vmAdminPassword
    vmSize: vmSize
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
    containerRegistryEndpoint: containerRegistryEndpoint
    imageTag: imageTag
    existingFoundryProjectResourceId: existingFoundryProjectResourceId
    existingLogAnalyticsWorkspaceId: existingLogAnalyticsWorkspaceId
  }
}

// ============================================================================
// Module: Vanilla Bicep Deployment (Docker)
// Activated when deploymentFlavor = 'bicep'
// ============================================================================

module bicepDeployment './bicep/main.bicep' = if (isBicep) {
  name: take('module.bicep.${solutionName}', 64)
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
    containerRegistryEndpoint: containerRegistryEndpoint
    imageTag: imageTag
    existingFoundryProjectResourceId: existingFoundryProjectResourceId
    existingLogAnalyticsWorkspaceId: existingLogAnalyticsWorkspaceId
  }
}

// ============================================================================
// Outputs — Coalesced from whichever flavor was deployed
// ============================================================================

@description('Solution suffix used for naming resources.')
output SOLUTION_NAME string = isBicep ? bicepDeployment!.outputs.SOLUTION_NAME : avmDeployment!.outputs.SOLUTION_NAME

@description('Name of the deployed resource group.')
output RESOURCE_GROUP_NAME string = resourceGroup().name

@description('Deployment flavor used.')
output DEPLOYMENT_FLAVOR string = deploymentFlavor

@description('The name of the web app container app.')
output CONTAINER_WEB_APP_NAME string = isBicep ? bicepDeployment!.outputs.CONTAINER_WEB_APP_NAME : avmDeployment!.outputs.CONTAINER_WEB_APP_NAME

@description('The FQDN of the web app container app.')
output CONTAINER_WEB_APP_FQDN string = isBicep ? bicepDeployment!.outputs.CONTAINER_WEB_APP_FQDN : avmDeployment!.outputs.CONTAINER_WEB_APP_FQDN

@description('The name of the API container app.')
output CONTAINER_API_APP_NAME string = isBicep ? bicepDeployment!.outputs.CONTAINER_API_APP_NAME : avmDeployment!.outputs.CONTAINER_API_APP_NAME

@description('The FQDN of the API container app.')
output CONTAINER_API_APP_FQDN string = isBicep ? bicepDeployment!.outputs.CONTAINER_API_APP_FQDN : avmDeployment!.outputs.CONTAINER_API_APP_FQDN

@description('Azure OpenAI service endpoint URL.')
output AZURE_OPENAI_ENDPOINT string = isBicep ? bicepDeployment!.outputs.AZURE_OPENAI_ENDPOINT : avmDeployment!.outputs.AZURE_OPENAI_ENDPOINT

@description('GPT model deployment name.')
output AZURE_ENV_GPT_MODEL_NAME string = isBicep ? bicepDeployment!.outputs.AZURE_ENV_GPT_MODEL_NAME : avmDeployment!.outputs.AZURE_ENV_GPT_MODEL_NAME

@description('Embedding model deployment name.')
output AZURE_ENV_EMBEDDING_DEPLOYMENT_NAME string = isBicep ? bicepDeployment!.outputs.AZURE_ENV_EMBEDDING_DEPLOYMENT_NAME : avmDeployment!.outputs.AZURE_ENV_EMBEDDING_DEPLOYMENT_NAME

@description('Cosmos DB account name.')
output AZURE_COSMOSDB_ACCOUNT string = isBicep ? bicepDeployment!.outputs.AZURE_COSMOSDB_ACCOUNT : avmDeployment!.outputs.AZURE_COSMOSDB_ACCOUNT

@description('Cosmos DB database name.')
output AZURE_COSMOSDB_DATABASE string = isBicep ? bicepDeployment!.outputs.AZURE_COSMOSDB_DATABASE : avmDeployment!.outputs.AZURE_COSMOSDB_DATABASE

@description('The Azure subscription ID.')
output AZURE_SUBSCRIPTION_ID string = isBicep ? bicepDeployment!.outputs.AZURE_SUBSCRIPTION_ID : avmDeployment!.outputs.AZURE_SUBSCRIPTION_ID

@description('The Azure resource group name.')
output AZURE_RESOURCE_GROUP string = isBicep ? bicepDeployment!.outputs.AZURE_RESOURCE_GROUP : avmDeployment!.outputs.AZURE_RESOURCE_GROUP

@description('Azure AI Agent service endpoint URL.')
output AZURE_AI_AGENT_ENDPOINT string = isBicep ? bicepDeployment!.outputs.AZURE_AI_AGENT_ENDPOINT : avmDeployment!.outputs.AZURE_AI_AGENT_ENDPOINT
