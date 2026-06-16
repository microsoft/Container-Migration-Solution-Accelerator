// ============================================================================
// main_custom.bicep — Standalone Vanilla Bicep Orchestrator
// Description: Pure orchestrator for Container Migration solution using vanilla
//              Bicep modules. Calls modules to deploy resources — no inline
//              resource definitions. All resource names derived from params.
//              For local/custom deployment without the deployment router.
// ============================================================================
targetScope = 'resourceGroup'

// ==============================================================================
// Parameters
// ==============================================================================

// ── Core ──

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
@description('Required. Location for AI Foundry and model deployments.')
param azureAiServiceLocation string

@description('Optional. Secondary location for Cosmos DB resources.')
param cosmosLocation string = 'eastus2'

// ── AI Configuration ──

@allowed([
  'Standard'
  'GlobalStandard'
])
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

@allowed([
  'Standard'
  'GlobalStandard'
])
@description('Optional. Embedding model deployment type.')
param embeddingDeploymentType string = 'GlobalStandard'

@description('Optional. Embedding model deployment capacity.')
param embeddingDeploymentCapacity int = 500

// ── Container Apps Configuration ──

@description('Optional. The endpoint (excluding https://) of an existing container registry.')
param containerRegistryEndpoint string = 'containermigrationacr.azurecr.io'

@description('Optional. The image tag to use for container images.')
param imageTag string = 'latest_v2'

// ── Identity ──

@description('Optional. Resource ID of an existing Foundry project.')
param existingFoundryProjectResourceId string = ''

@description('Optional. Existing Log Analytics Workspace Resource ID.')
param existingLogAnalyticsWorkspaceId string = ''

@description('Optional. The tags to apply to all deployed Azure resources.')
param tags object = {}

// ==============================================================================
// Variables
// ==============================================================================

var solutionLocation = empty(location) ? resourceGroup().location : location

var solutionSuffix = toLower(trim(replace(
  replace(
    replace(replace(replace(replace('${solutionName}${solutionUniqueText}', '-', ''), '_', ''), '.', ''), '/', ''),
    ' ',
    ''
  ),
  '*',
  ''
)))

var deployerInfo = deployer()
var deployingUserPrincipalId = deployerInfo.objectId
var deployingUserPrincipalType = contains(deployerInfo, 'userPrincipalName') ? 'User' : 'ServicePrincipal'

var createdBy = contains(deployerInfo, 'userPrincipalName')
  ? split(deployerInfo.userPrincipalName, '@')[0]
  : deployerInfo.objectId

var existingTags = resourceGroup().tags ?? {}
var useExistingLogAnalytics = !empty(existingLogAnalyticsWorkspaceId)

var aiModelDeployments = [
  {
    name: gptModelName
    model: gptModelName
    sku: {
      name: deploymentType
      capacity: gptDeploymentCapacity
    }
    version: gptModelVersion
    raiPolicyName: 'Microsoft.Default'
  }
  {
    name: embeddingModel
    model: embeddingModel
    sku: {
      name: embeddingDeploymentType
      capacity: embeddingDeploymentCapacity
    }
    version: embeddingModelVersion
    raiPolicyName: 'Microsoft.Default'
  }
]

// Cosmos DB containers for migration solution
var cosmosDatabaseName = 'migration_db'
var cosmosContainers = [
  { name: 'processes', partitionKeyPath: '/_partitionKey' }
  { name: 'agent_telemetry', partitionKeyPath: '/_partitionKey' }
  { name: 'processcontrol', partitionKeyPath: '/_partitionKey' }
  { name: 'files', partitionKeyPath: '/_partitionKey' }
  { name: 'process_statuses', partitionKeyPath: '/_partitionKey' }
]

// Storage containers
var processBlobContainerName = 'processes'
var processQueueName = 'processes-queue'

// ========== Resource Group Tag ========== //
resource resourceGroupTags 'Microsoft.Resources/tags@2023-07-01' = {
  name: 'default'
  properties: {
    tags: union(
      existingTags,
      tags,
      {
        TemplateName: 'Container Migration'
        CreatedBy: createdBy
        DeploymentName: deployment().name
        Type: 'Non-WAF'
      }
    )
  }
}

// ========== Monitoring (Log Analytics) ========== //

module log_analytics './bicep/modules/monitoring/log-analytics.bicep' = if (!useExistingLogAnalytics) {
  name: take('module.log-analytics.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: solutionLocation
  }
  scope: resourceGroup(resourceGroup().name)
}

var logAnalyticsWorkspaceResourceId = useExistingLogAnalytics
  ? existingLogAnalyticsWorkspaceId
  : log_analytics!.outputs.resourceId

// ========== AI Foundry and related resources ========== //

// Deploy new AI Services account + AI Foundry project (no connections, no deployments)
module ai_foundry_project './bicep/modules/ai/ai-foundry-project.bicep' = if (empty(existingFoundryProjectResourceId)) {
  name: take('module.ai-foundry-project.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: azureAiServiceLocation
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Unified AI Foundry resource name vars ========== //
var useExistingAIProject = !empty(existingFoundryProjectResourceId)
var aiFoundryResourceName = useExistingAIProject ? split(existingFoundryProjectResourceId, '/')[8] : ai_foundry_project!.outputs.name
var aiProjectResourceName = useExistingAIProject ? split(existingFoundryProjectResourceId, '/')[10] : ai_foundry_project!.outputs.projectName
var aiServiceSubscription = useExistingAIProject ? split(existingFoundryProjectResourceId, '/')[2] : subscription().subscriptionId
var aiServiceResourceGroup = useExistingAIProject ? split(existingFoundryProjectResourceId, '/')[4] : resourceGroup().name

// Reference existing AI Foundry project (identity only)
module existing_project_setup './bicep/modules/ai/existing-project-setup.bicep' = if (useExistingAIProject) {
  name: take('module.existing-project-setup.${solutionName}', 64)
  scope: resourceGroup(aiServiceSubscription, aiServiceResourceGroup)
  params: {
    name: aiFoundryResourceName
    projectName: aiProjectResourceName
  }
}

// Storage Blob connection (single call for both existing and new paths)
module foundry_storage_connection './bicep/modules/ai/ai-foundry-connection.bicep' = {
  name: take('module.foundry-storage-conn.${solutionName}', 64)
  scope: resourceGroup(aiServiceSubscription, aiServiceResourceGroup)
  params: {
    solutionName: solutionSuffix
    aiServicesAccountName: aiFoundryResourceName
    projectName: aiProjectResourceName
    category: 'AzureBlob'
    target: storage_account.outputs.blobEndpoint
    authType: 'AAD'
    metadata: {
      ResourceId: storage_account.outputs.resourceId
      AccountName: storage_account.outputs.name
      ContainerName: 'default'
    }
  }
}

// Model deployments (single loop for both existing and new paths)
@batchSize(1)
module model_deployments './bicep/modules/ai/ai-foundry-model-deployment.bicep' = [for (deployment, i) in aiModelDeployments: {
  name: take('module.model-deployment-${i}.${solutionName}', 64)
  scope: resourceGroup(aiServiceSubscription, aiServiceResourceGroup)
  params: {
    aiServicesAccountName: aiFoundryResourceName
    deploymentName: deployment.name
    modelName: deployment.model
    modelVersion: deployment.version
    raiPolicyName: deployment.raiPolicyName
    skuName: deployment.sku.name
    skuCapacity: deployment.sku.capacity
  }
}]

// ========== AI outputs (ternary: existing vs new) ========== //
var aiFoundryEndpoint = useExistingAIProject ? existing_project_setup!.outputs.cognitiveServicesEndpoint : ai_foundry_project!.outputs.cognitiveServicesEndpoint
var projectEndpoint = useExistingAIProject ? existing_project_setup!.outputs.projectEndpoint : ai_foundry_project!.outputs.projectEndpoint
var aiFoundryResourceId = !useExistingAIProject ? ai_foundry_project!.outputs.resourceId : ''
var aiProjectPrincipalId = useExistingAIProject ? existing_project_setup!.outputs.projectIdentityPrincipalId : ai_foundry_project!.outputs.projectIdentityPrincipalId

// ========== Storage Account module ========== //
module storage_account './bicep/modules/data/storage-account.bicep' = {
  name: take('module.storage-account.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: solutionLocation
    tags: tags
    containers: [
      { name: 'data', publicAccess: 'None' }
    ]
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Cosmos DB module ========== //
module cosmosDBModule './bicep/modules/data/cosmos-db-nosql.bicep' = {
  name: take('module.cosmos-db.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    name: 'cosmos-${solutionSuffix}'
    location: cosmosLocation
    databaseName: cosmosDatabaseName
    containers: cosmosContainers
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Container App Environment ========== //
module containerAppEnv './bicep/modules/compute/container-app-environment.bicep' = {
  name: take('module.container-app-env.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: solutionLocation
    tags: union(existingTags, tags, { TemplateName: 'Container Migration' })
    logAnalyticsWorkspaceResourceId: logAnalyticsWorkspaceResourceId
  }
}

// ========== Container Apps ========== //
var backendContainerAppName = take('ca-backend-api-${solutionSuffix}', 32)
var processorContainerAppName = take('ca-processor-${solutionSuffix}', 32)
var frontEndContainerAppName = take('ca-frontend-${solutionSuffix}', 32)

// ========== Backend API Container App ========== //
module ca_backend_api './bicep/modules/compute/container-app.bicep' = {
  name: take('module.ca-backend-api.${solutionName}', 64)
  params: {
    name: backendContainerAppName
    location: solutionLocation
    tags: union(existingTags, tags, { TemplateName: 'Container Migration' })
    environmentResourceId: containerAppEnv.outputs.resourceId
    managedIdentities: { systemAssigned: true }
    ingressExternal: true
    ingressTargetPort: 80
    containers: [
      {
        name: 'backend-api'
        image: '${containerRegistryEndpoint}/backend-api:${imageTag}'
        env: [
          { name: 'AZURE_OPENAI_ENDPOINT', value: aiFoundryEndpoint }
          { name: 'AZURE_OPENAI_CHAT_DEPLOYMENT_NAME', value: gptModelName }
          { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME', value: embeddingModel }
          { name: 'AZURE_OPENAI_API_VERSION', value: '2025-03-01-preview' }
          { name: 'COSMOS_DB_ACCOUNT_URL', value: cosmosDBModule.outputs.endpoint }
          { name: 'COSMOS_DB_DATABASE_NAME', value: cosmosDatabaseName }
          { name: 'COSMOS_DB_CONTAINER_NAME', value: 'agent_telemetry' }
          { name: 'COSMOS_DB_CONTROL_CONTAINER_NAME', value: 'processcontrol' }
          { name: 'COSMOS_DB_PROCESS_CONTAINER', value: 'processes' }
          { name: 'COSMOS_DB_PROCESS_LOG_CONTAINER', value: 'agent_telemetry' }
          { name: 'STORAGE_ACCOUNT_BLOB_URL', value: storage_account.outputs.blobEndpoint }
          { name: 'STORAGE_ACCOUNT_NAME', value: storage_account.outputs.name }
          { name: 'STORAGE_ACCOUNT_PROCESS_CONTAINER', value: processBlobContainerName }
          { name: 'STORAGE_ACCOUNT_PROCESS_QUEUE', value: processQueueName }
          { name: 'STORAGE_ACCOUNT_QUEUE_URL', value: '${storage_account.outputs.serviceEndpoints.queue}' }
          { name: 'GLOBAL_LLM_SERVICE', value: 'AzureOpenAI' }
          { name: 'PROCESSOR_CONTROL_URL', value: 'https://${processorContainerAppName}.internal.${containerAppEnv.outputs.defaultDomain}' }
          { name: 'APP_ENV', value: 'Prod' }
        ]
        resources: {
          cpu: json('1')
          memory: '2.0Gi'
        }
      }
    ]
    corsPolicy: {
      allowedOrigins: ['*']
      allowedMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
      allowedHeaders: ['Authorization', 'Content-Type', '*']
    }
    scaleSettings: {
      maxReplicas: 1
      minReplicas: 1
    }
  }
}

// ========== Frontend Container App ========== //
module ca_frontend './bicep/modules/compute/container-app.bicep' = {
  name: take('module.ca-frontend.${solutionName}', 64)
  params: {
    name: frontEndContainerAppName
    location: solutionLocation
    tags: union(existingTags, tags, { TemplateName: 'Container Migration' })
    environmentResourceId: containerAppEnv.outputs.resourceId
    managedIdentities: { systemAssigned: true }
    ingressExternal: true
    ingressTargetPort: 3000
    containers: [
      {
        name: 'frontend'
        image: '${containerRegistryEndpoint}/frontend:${imageTag}'
        env: [
          { name: 'API_URL', value: 'https://${ca_backend_api.outputs.fqdn}' }
          { name: 'APP_ENV', value: 'prod' }
          { name: 'REACT_APP_MSAL_POST_REDIRECT_URL', value: '/' }
          { name: 'REACT_APP_MSAL_REDIRECT_URL', value: '/' }
          { name: 'ALLOWED_ORIGINS', value: 'https://${frontEndContainerAppName}.${containerAppEnv.outputs.defaultDomain}' }
        ]
        resources: {
          cpu: json('1')
          memory: '2.0Gi'
        }
      }
    ]
    scaleSettings: {
      maxReplicas: 1
      minReplicas: 1
    }
  }
}

// ========== Processor Container App ========== //
module ca_processor './bicep/modules/compute/container-app.bicep' = {
  name: take('module.ca-processor.${solutionName}', 64)
  params: {
    name: processorContainerAppName
    location: solutionLocation
    tags: union(existingTags, tags, { TemplateName: 'Container Migration' })
    environmentResourceId: containerAppEnv.outputs.resourceId
    managedIdentities: { systemAssigned: true }
    ingressExternal: false
    ingressTargetPort: 8080
    ingressAllowInsecure: true
    containers: [
      {
        name: 'processor'
        image: '${containerRegistryEndpoint}/processor:${imageTag}'
        env: [
          { name: 'AZURE_OPENAI_ENDPOINT', value: aiFoundryEndpoint }
          { name: 'AZURE_OPENAI_CHAT_DEPLOYMENT_NAME', value: gptModelName }
          { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME', value: embeddingModel }
          { name: 'AZURE_OPENAI_API_VERSION', value: '2025-03-01-preview' }
          { name: 'COSMOS_DB_ACCOUNT_URL', value: cosmosDBModule.outputs.endpoint }
          { name: 'COSMOS_DB_DATABASE_NAME', value: cosmosDatabaseName }
          { name: 'COSMOS_DB_CONTAINER_NAME', value: 'agent_telemetry' }
          { name: 'COSMOS_DB_CONTROL_CONTAINER_NAME', value: 'processcontrol' }
          { name: 'COSMOS_DB_PROCESS_CONTAINER', value: 'processes' }
          { name: 'COSMOS_DB_PROCESS_LOG_CONTAINER', value: 'agent_telemetry' }
          { name: 'STORAGE_ACCOUNT_BLOB_URL', value: storage_account.outputs.blobEndpoint }
          { name: 'STORAGE_ACCOUNT_NAME', value: storage_account.outputs.name }
          { name: 'STORAGE_QUEUE_ACCOUNT', value: storage_account.outputs.name }
          { name: 'STORAGE_ACCOUNT_PROCESS_CONTAINER', value: processBlobContainerName }
          { name: 'STORAGE_ACCOUNT_PROCESS_QUEUE', value: processQueueName }
          { name: 'STORAGE_ACCOUNT_QUEUE_URL', value: '${storage_account.outputs.serviceEndpoints.queue}' }
          { name: 'GLOBAL_LLM_SERVICE', value: 'AzureOpenAI' }
          { name: 'CONTROL_API_ENABLED', value: '1' }
          { name: 'CONTROL_API_PORT', value: '8080' }
        ]
        resources: {
          cpu: json('2')
          memory: '4.0Gi'
        }
      }
    ]
    scaleSettings: {
      maxReplicas: 1
      minReplicas: 1
    }
  }
}

// ========== Role Assignments ========== //
module role_assignments './bicep/modules/identity/role-assignments.bicep' = {
  name: take('module.role-assignments.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    useExistingAIProject: useExistingAIProject
    existingFoundryProjectResourceId: existingFoundryProjectResourceId
    aiFoundryResourceId: !useExistingAIProject ? aiFoundryResourceId : ''
    aiSearchResourceId: ''
    storageAccountResourceId: storage_account.outputs.resourceId
    aiProjectPrincipalId: aiProjectPrincipalId
    aiSearchPrincipalId: ''
    deployerPrincipalId: deployingUserPrincipalId
    deployerPrincipalType: deployingUserPrincipalType
    backendAppServicePrincipalId: ca_backend_api.outputs.principalId
    processorAppServicePrincipalId: ca_processor.outputs.principalId
    cosmosDbAccountName: cosmosDBModule.outputs.name
  }
  scope: resourceGroup(resourceGroup().name)
}

// ==============================================================================
// Outputs
// ==============================================================================

@description('Solution suffix used for naming resources')
output SOLUTION_NAME string = solutionSuffix

@description('Name of the deployed resource group')
output RESOURCE_GROUP_NAME string = resourceGroup().name

@description('The name of the web app container app.')
output CONTAINER_WEB_APP_NAME string = ca_frontend.outputs.name

@description('The FQDN of the web app container app.')
output CONTAINER_WEB_APP_FQDN string = ca_frontend.outputs.fqdn

@description('The name of the API container app.')
output CONTAINER_API_APP_NAME string = ca_backend_api.outputs.name

@description('The FQDN of the API container app.')
output CONTAINER_API_APP_FQDN string = ca_backend_api.outputs.fqdn

@description('Azure OpenAI service endpoint URL')
output AZURE_OPENAI_ENDPOINT string = aiFoundryEndpoint

@description('GPT model deployment name')
output AZURE_ENV_GPT_MODEL_NAME string = gptModelName

@description('Embedding model deployment name')
output AZURE_ENV_EMBEDDING_DEPLOYMENT_NAME string = embeddingModel

@description('Cosmos DB account name')
output AZURE_COSMOSDB_ACCOUNT string = cosmosDBModule.outputs.name

@description('Cosmos DB database name')
output AZURE_COSMOSDB_DATABASE string = cosmosDatabaseName

@description('The Azure subscription ID.')
output AZURE_SUBSCRIPTION_ID string = subscription().subscriptionId

@description('The Azure resource group name.')
output AZURE_RESOURCE_GROUP string = resourceGroup().name

@description('Azure AI Agent service endpoint URL')
output AZURE_AI_AGENT_ENDPOINT string = projectEndpoint
