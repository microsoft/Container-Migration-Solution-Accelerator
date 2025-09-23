targetScope = 'resourceGroup'

@minLength(3)
@maxLength(16)
@description('Required. A unique application/solution name for all resources in this deployment. This should be 3-16 characters long.')
param solutionName string

@maxLength(5)
@description('Optional. A unique text/token for the solution. This is used to ensure resource names are unique for global resources. Defaults to a 5-character substring of the unique string generated from the subscription ID, resource group name, and solution name.')
param solutionUniqueText string = substring(uniqueString(subscription().id, resourceGroup().name, solutionName), 0, 5)

@minLength(3)
@metadata({ azd: { type: 'location' } })
@description('Optional. Azure region for all services. Defaults to the resource group location.')
param location string = resourceGroup().location

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
  azd : {
    type: 'location'
    usageName : [
      'OpenAI.GlobalStandard.o3, 500'
    ]
  }
})
@description('Optional. Location for all AI service resources. This location can be different from the resource group location.')
param aiDeploymentLocation string?

@description('Optional. The host (excluding https://) of an existing container registry. This is the `loginServer` when using Azure Container Registry.')
param containerRegistryHost string = 'containermigrationacr.azurecr.io'

@minLength(1)
@allowed(['Standard', 'GlobalStandard'])
@description('Optional. Model deployment type. Defaults to GlobalStandard.')
param aiDeploymentType string = 'GlobalStandard'

@minLength(1)
@description('Optional. Name of the AI model to deploy. Recommend using o3. Defaults to o3.')
param aiModelName string = 'o3'

@minLength(1)
@description('Optional. Version of AI model. Review available version numbers per model before setting. Defaults to 2025-04-16.')
param aiModelVersion string = '2025-04-16'

@description('Optional. AI model deployment token capacity. Defaults to 500K tokens per minute.')
param aiModelCapacity int = 500

@description('Optional. Specifies the resource tags for all the resources. Tag "azd-env-name" is automatically added to all resources.')
param tags object = {}

@description('Optional. Enable monitoring for the resources. This will enable Application Insights and Log Analytics. Defaults to false.')
param enableMonitoring bool = false

@description('Optional. Enable scaling for the container apps. Defaults to false.')
param enableScaling bool = false

@description('Optional. Enable redundancy for applicable resources. Defaults to false.')
param enableRedundancy bool = false

@metadata({ azd: { type: 'location' } })
@description('Optional. The secondary location for the Cosmos DB account if redundancy is enabled.')
param secondaryLocation string?

@description('Optional. Enable private networking for the resources. Defaults to false.')
param enablePrivateNetworking bool = false

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

var resourcesName = toLower(trim(replace(
  replace(
    replace(replace(replace(replace('${solutionName}${solutionUniqueText}', '-', ''), '_', ''), '.', ''), '/', ''),
    ' ',
    ''
  ),
  '*',
  ''
)))

var allTags = union(
  {
    'azd-env-name': solutionName
    TemplateName: 'Container Migration'
  },
  tags
)

resource resourceGroupTags 'Microsoft.Resources/tags@2021-04-01' = {
  name: 'default'
  properties: {
    tags: union(
      reference(resourceGroup().id, '2021-04-01', 'Full').?tags ?? {},
      allTags
    )
  }
}

module logAnalyticsWorkspace 'br/public:avm/res/operational-insights/workspace:0.12.0' = if (enableMonitoring || enablePrivateNetworking) {
  name: take('avm.res.operational-insights.workspace.${resourcesName}', 64)
  params: {
    name: 'log-${resourcesName}'
    location: location
    skuName: 'PerGB2018'
    dataRetention: 30
    diagnosticSettings: [{ useThisWorkspace: true }]
    tags: allTags
    enableTelemetry: enableTelemetry
  }
}

module applicationInsights 'br/public:avm/res/insights/component:0.6.0' = if (enableMonitoring) {
  name: take('avm.res.insights.component.${resourcesName}', 64)
  #disable-next-line no-unnecessary-dependson
  dependsOn: [logAnalyticsWorkspace]
  params: {
    name: 'appi-${resourcesName}'
    location: location
    workspaceResourceId: logAnalyticsWorkspace!.outputs!.resourceId
    diagnosticSettings: [{ workspaceResourceId: logAnalyticsWorkspace!.outputs!.resourceId }]
    tags: allTags
    enableTelemetry: enableTelemetry
  }
}

resource appIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: 'id-${resourcesName}'
  location: location
  tags: allTags
}

var processBlobContainerName = 'processes'
var processQueueName = 'processes-queue'

module storageAccount 'modules/storageAccount.bicep' = {
  name: take('module.storageAccount.${resourcesName}', 64)
  #disable-next-line no-unnecessary-dependson
  dependsOn: [logAnalyticsWorkspace]
  params: {
    name: take('sa${resourcesName}', 24)
    location: location
    skuName: enableRedundancy ? 'Standard_GZRS' : 'Standard_LRS'
    // TODO - private networking
    // privateEndpointSubnetResourceId: privateEndpointSubnetResourceId
    // blobPrivateDnsZoneResourceId: blobPrivateDnsZoneResourceId
    // queuePrivateDnsZoneResourceId: queuePrivateDnsZoneResourceId
    containers: [processBlobContainerName]
    queues: [processQueueName, '${processQueueName}-dead-letter']
    logAnalyticsWorkspaceResourceId: enableMonitoring ? logAnalyticsWorkspace!.outputs!.resourceId : ''
    roleAssignments: [
      {
        roleDefinitionIdOrName: 'Storage Blob Data Contributor'
        principalId: appIdentity.properties.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: 'Storage Queue Data Contributor'
        principalId: appIdentity.properties.principalId
        principalType: 'ServicePrincipal'
      }
    ]
    enableTelemetry: enableTelemetry
    tags: allTags
  }
}

var cosmosDatabaseName = 'migration_db'
var processCosmosContainerName = 'processes'
var agentTelemetryCosmosContainerName = 'agent_telemetry'

module cosmosDb 'modules/cosmosDb.bicep' = {
  name: take('module.cosmosdb.${resourcesName}', 64)
  #disable-next-line no-unnecessary-dependson
  dependsOn: [logAnalyticsWorkspace]
  params: {
    name: take('cosmos-${resourcesName}', 44)
    location: location
    zoneRedundant: enableRedundancy
    secondaryLocation: enableRedundancy && !empty(secondaryLocation) ? secondaryLocation : ''
    databaseName: cosmosDatabaseName
    containers: [
      processCosmosContainerName
      agentTelemetryCosmosContainerName
      'files'
      'process_statuses'
    ]
    // TODO - private networking
    // privateEndpointSubnetResourceId: privateEndpointSubnetResourceId
    // sqlPrivateDnsZoneResourceId: sqlPrivateDnsZoneResourceId
    dataAccessIdentityPrincipalId: appIdentity.properties.principalId
    logAnalyticsWorkspaceResourceId: enableMonitoring ? logAnalyticsWorkspace!.outputs!.resourceId : ''
    enableTelemetry: enableTelemetry
    tags: allTags
  }
}

var aiModelDeploymentName = aiModelName

module aiFoundry 'br/public:avm/ptn/ai-ml/ai-foundry:0.3.0' = {
  name: take('avm.ptn.ai-ml.ai-foundry.${resourcesName}', 64)
  params: {
    #disable-next-line BCP334
    baseName: take(resourcesName, 12)
    baseUniqueName: null
    location: empty(aiDeploymentLocation) ? location : aiDeploymentLocation
    aiFoundryConfiguration: {
      allowProjectManagement: true
      roleAssignments: [
        {
          principalId: appIdentity.properties.principalId
          principalType: 'ServicePrincipal'
          roleDefinitionIdOrName: 'Cognitive Services OpenAI Contributor'
        }
        {
          principalId: appIdentity.properties.principalId
          principalType: 'ServicePrincipal'
          roleDefinitionIdOrName: '64702f94-c441-49e6-a78b-ef80e0188fee' // Azure AI Developer
        }
        {
          principalId: appIdentity.properties.principalId
          principalType: 'ServicePrincipal'
          roleDefinitionIdOrName: '53ca6127-db72-4b80-b1b0-d745d6d5456d' // Azure AI User
        }
      ]
      // TODO - private networking
      // networking: {
      //   aiServicesPrivateDnsZoneId: ''
      //   openAiPrivateDnsZoneId: ''
      //   cognitiveServicesPrivateDnsZoneId: ''
      // }
    }
    // TODO - private networking
    //privateEndpointSubnetId:
    aiModelDeployments: [
      {
        name: aiModelDeploymentName
        model: {
          format: 'OpenAI'
          name: aiModelName
          version: aiModelVersion
        }
        sku: {
          name: aiDeploymentType
          capacity: aiModelCapacity
        }
      }
    ]
    tags: allTags
    enableTelemetry: enableTelemetry
  }
}

module appConfiguration 'br/public:avm/res/app-configuration/configuration-store:0.9.1' = {
  name: take('avm.res.app-config.store.${resourcesName}', 64)
  params: {
    location: location
    name: 'appcs-${resourcesName}'
    disableLocalAuth: true
    enablePurgeProtection: false
    // TODO - private networking
    //privateEndpoints:
    tags: allTags
    keyValues: [
      {
        name: 'APP_LOGGING_ENABLE'
        value: 'true'
      }
      {
        name: 'APP_LOGGING_LEVEL'
        value: 'INFO'
      }
      {
        name: 'AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME'
        value: ''
      }
      {
        name: 'AZURE_AI_AGENT_PROJECT_CONNECTION_STRING'
        value: ''
      }
      {
        name: 'AZURE_OPENAI_API_VERSION'
        value: '2025-01-01-preview'
      }
      {
        name: 'AZURE_OPENAI_CHAT_DEPLOYMENT_NAME'
        value: aiModelDeploymentName
      }
      {
        name: 'AZURE_OPENAI_ENDPOINT'
        value: 'https://${aiFoundry.outputs.aiServicesName}.cognitiveservices.azure.com/'
      }
      {
        name: 'AZURE_OPENAI_ENDPOINT_BASE'
        value: 'https://${aiFoundry.outputs.aiServicesName}.cognitiveservices.azure.com/'
      }
      {
        name: 'AZURE_TRACING_ENABLED'
        value: 'True'
      }
      {
        name: 'STORAGE_ACCOUNT_BLOB_URL'
        value: storageAccount.outputs.blobEndpoint
      }
      {
        name: 'STORAGE_ACCOUNT_NAME'
        value: storageAccount.outputs.name
      }
      {
        name: 'STORAGE_ACCOUNT_PROCESS_CONTAINER'
        value: processBlobContainerName
      }
      {
        name: 'STORAGE_ACCOUNT_PROCESS_QUEUE'
        value: processQueueName
      }
      {
        name: 'STORAGE_ACCOUNT_QUEUE_URL'
        value: storageAccount.outputs.queueEndpoint
      }
      {
        name: 'COSMOS_DB_CONTAINER_NAME'
        value: agentTelemetryCosmosContainerName
      }
      {
        name: 'COSMOS_DB_DATABASE_NAME'
        value: cosmosDatabaseName
      }
      {
        name: 'COSMOS_DB_ACCOUNT_URL'
        value: cosmosDb.outputs.endpoint
      }
      {
        name: 'COSMOS_DB_PROCESS_CONTAINER'
        value: processCosmosContainerName
      }
      {
        name: 'COSMOS_DB_PROCESS_LOG_CONTAINER' // TODO - is this being used?
        value: agentTelemetryCosmosContainerName
      }
      {
        name: 'GLOBAL_LLM_SERVICE'
        value: 'AzureOpenAI'
      }
      {
        name: 'STORAGE_QUEUE_ACCOUNT' // TODO - is this being used?
        value: storageAccount.outputs.name
      }
    ]
    roleAssignments: [
      {
        principalId: appIdentity.properties.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: 'App Configuration Data Reader'
      }
    ]
    enableTelemetry: enableTelemetry
  }
}

var containerAppsEnvironmentName = 'cae-${resourcesName}'
module containerAppsEnvironment 'br/public:avm/res/app/managed-environment:0.11.3' = {
  name: take('avm.res.app.managed-environment.${containerAppsEnvironmentName}', 64)
  #disable-next-line no-unnecessary-dependson
  dependsOn: [logAnalyticsWorkspace, applicationInsights] // required due to optional flags that could change dependency
  params: {
    name: containerAppsEnvironmentName
    infrastructureResourceGroupName: '${resourceGroup().name}-ME-${containerAppsEnvironmentName}'
    location: location
    zoneRedundant: enableRedundancy && enablePrivateNetworking
    publicNetworkAccess: 'Enabled' // public access required for frontend
    // TODO - private networking:
    //infrastructureSubnetResourceId: enablePrivateNetworking ? network.outputs.subnetWebResourceId : null
    managedIdentities: {
      userAssignedResourceIds: [
        appIdentity.id
      ]
    }
    appInsightsConnectionString: enableMonitoring ? applicationInsights!.outputs.connectionString : null
    appLogsConfiguration: enableMonitoring ? {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace!.outputs!.logAnalyticsWorkspaceId
        sharedKey: logAnalyticsWorkspace!.outputs!.primarySharedKey
      }
    } : {}
    // TODO - private networking:
    // workloadProfiles: enablePrivateNetworking
    //   ? [
    //       // NOTE: workload profiles are required for private networking
    //       {
    //         name: 'Consumption'
    //         workloadProfileType: 'Consumption'
    //       }
    //     ]
    //   : []
    tags: allTags
    enableTelemetry: enableTelemetry
  }
}

var backendContainerPort = 80
var backendContainerAppName = take('ca-backend-api-${resourcesName}', 32)
module containerAppBackend 'br/public:avm/res/app/container-app:0.18.1' = {
  name: take('avm.res.app.container-app.${backendContainerAppName}', 64)
  #disable-next-line no-unnecessary-dependson
  dependsOn: [applicationInsights]
  params: {
    name: backendContainerAppName
    location: location
    environmentResourceId: containerAppsEnvironment.outputs.resourceId
    managedIdentities: {
      userAssignedResourceIds: [
        appIdentity.id
      ]
    }
    containers: [
      {
        name: 'backend-api'
        image: '${containerRegistryHost}/backend-api:latest'
        env: concat(
          [
            {
              name: 'APP_CONFIGURATION_URL'
              value: appConfiguration.outputs.endpoint
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: appIdentity.properties.clientId
            }
          ],
          enableMonitoring
            ? [
                {
                  name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
                  value: applicationInsights!.outputs.connectionString
                }
              ]
            : []
        )
        resources: {
          cpu: 1
          memory: '2.0Gi'
        }
      }
    ]
    ingressTargetPort: backendContainerPort
    ingressExternal: true
    scaleSettings: {
      maxReplicas: enableScaling ? 3 : 1
      minReplicas: 1
      rules: enableScaling ? [
        {
          name: 'http-scaler'
          http: {
            metadata: {
              concurrentRequests: 100
            }
          }
        }
      ] : []
    }
    corsPolicy: {
      allowedOrigins: [
        '*'
      ]
      allowedMethods: [
        'GET'
        'POST'
        'PUT'
        'DELETE'
        'OPTIONS'
      ]
      allowedHeaders: [
        'Authorization'
        'Content-Type'
        '*'
      ]
    }
    tags: allTags
    enableTelemetry: enableTelemetry
  }
}

var frontEndContainerAppName = take('ca-frontend-${resourcesName}', 32)
module containerAppFrontend 'br/public:avm/res/app/container-app:0.18.1' = {
  name: take('avm.res.app.container-app.${frontEndContainerAppName}', 64)
  params: {
    name: frontEndContainerAppName
    location: location
    environmentResourceId: containerAppsEnvironment.outputs.resourceId
    managedIdentities: {
      userAssignedResourceIds: [
        appIdentity.id
      ]
    }
    containers: [
      {
        name: 'frontend'
        image: '${containerRegistryHost}/frontend:latest'
        env: [
          {
            name: 'API_URL'
            value: 'https://${containerAppBackend.outputs.fqdn}'
          }
          {
            name: 'APP_ENV'
            value: 'prod'
          }
        ]
        resources: {
          cpu: '1'
          memory: '2.0Gi'
        }
      }
    ]
    ingressTargetPort: 3000
    ingressExternal: true
    scaleSettings: {
      maxReplicas: enableScaling ? 3 : 1
      minReplicas: 1
      rules: enableScaling ? [
        {
          name: 'http-scaler'
          http: {
            metadata: {
              concurrentRequests: 100
            }
          }
        }
      ] : []
    }
    tags: allTags
    enableTelemetry: enableTelemetry
  }
}

var processorContainerAppName = take('ca-processor-${resourcesName}', 32)
module containerAppProcessor 'br/public:avm/res/app/container-app:0.18.1' = {
  name: take('avm.res.app.container-app.${processorContainerAppName}', 64)
  #disable-next-line no-unnecessary-dependson
  dependsOn: [applicationInsights]
  params: {
    name: processorContainerAppName
    location: location
    environmentResourceId: containerAppsEnvironment.outputs.resourceId
    managedIdentities: {
      userAssignedResourceIds: [
        appIdentity.id
      ]
    }
    containers: [
      {
        name: 'processor'
        image: '${containerRegistryHost}/processor:latest'
        env: concat(
          [
            {
              name: 'APP_CONFIGURATION_URL'
              value: appConfiguration.outputs.endpoint
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: appIdentity.properties.clientId
            }
            {
              name: 'AZURE_STORAGE_ACCOUNT_NAME' // TODO - verify name and if needed or if pulled from app config service
              value: storageAccount.outputs.name
            }
            {
              name: 'STORAGE_ACCOUNT_NAME' // TODO - verify name and if needed 
              value: storageAccount.outputs.name
            }
          ],
          enableMonitoring
            ? [
                {
                  name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
                  value: applicationInsights!.outputs.connectionString
                }
              ]
            : []
        )
        resources: { // TODO - assess increasing resource limits
          cpu: 2
          memory: '4.0Gi'
        }
      }
    ]
    ingressTransport: null
    disableIngress: true
    ingressExternal: false
    scaleSettings: {
      maxReplicas: enableScaling ? 3 : 1
      minReplicas: 1
      //rules: [] - TODO - what scaling rules to use here?
    }
    tags: allTags
    enableTelemetry: enableTelemetry
  }
}

@description('The name of the resource group.')
output resourceGroupName string = resourceGroup().name
