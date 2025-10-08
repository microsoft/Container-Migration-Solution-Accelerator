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
param location string
var solutionLocation = empty(location) ? resourceGroup().location : location

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

@description('Required. Location for AI Foundry deployment. This is the location where the AI Foundry resources will be deployed.')
param azureAiServiceLocation string

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

@description('Optional. The tags to apply to all deployed Azure resources.')
param tags resourceInput<'Microsoft.Resources/resourceGroups@2025-04-01'>.tags = {}

@description('Optional. Enable scaling for the container apps. Defaults to false.')
param enableScaling bool = false

@description('Optional. Enable redundancy for applicable resources. Defaults to false.')
param enableRedundancy bool = false

@metadata({ azd: { type: 'location' } })
@description('Optional. The secondary location for the Cosmos DB account if redundancy is enabled.')
param secondaryLocation string?

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Optional. Enable private networking for applicable resources, aligned with the Well Architected Framework recommendations. Defaults to false.')
param enablePrivateNetworking bool = false

@description('Optional. Enable monitoring applicable resources, aligned with the Well Architected Framework recommendations. This setting enables Application Insights and Log Analytics and configures all the resources applicable resources to send logs. Defaults to false.')
param enableMonitoring bool = false

@description('Optional. Enable scalability for applicable resources, aligned with the Well Architected Framework recommendations. Defaults to false.')
param enableScalability bool = false

@description('Optional. CosmosDB Location')
param cosmosLocation string = 'eastus2'

@description('Optional. Existing Log Analytics Workspace Resource ID')
param existingLogAnalyticsWorkspaceId string = ''

// Extracts subscription, resource group, and workspace name from the resource ID when using an existing Log Analytics workspace
var useExistingLogAnalytics = !empty(existingLogAnalyticsWorkspaceId)
var existingLawSubscription = useExistingLogAnalytics ? split(existingLogAnalyticsWorkspaceId, '/')[2] : ''
var existingLawResourceGroup = useExistingLogAnalytics ? split(existingLogAnalyticsWorkspaceId, '/')[4] : ''
var existingLawName = useExistingLogAnalytics ? split(existingLogAnalyticsWorkspaceId, '/')[8] : ''

// resource existingLogAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2020-08-01' existing = if (useExistingLogAnalytics) {
//   name: existingLawName
//   scope: resourceGroup(existingLawSubscription, existingLawResourceGroup)
// }

var logAnalyticsWorkspaceResourceId = useExistingLogAnalytics  ? existingLogAnalyticsWorkspaceId  : logAnalyticsWorkspace!.outputs.resourceId

@description('Tag, Created by user name')
param createdBy string = contains(deployer(), 'userPrincipalName')? split(deployer().userPrincipalName, '@')[0]: deployer().objectId

@description('Optional. Resource ID of an existing Foundry project')
param existingFoundryProjectResourceId string = ''

@description('Optional. Admin username for the Jumpbox Virtual Machine. Set to custom value if enablePrivateNetworking is true.')
@secure()
//param vmAdminUsername string = take(newGuid(), 20)
param vmAdminUsername string?

@description('Optional. Admin password for the Jumpbox Virtual Machine. Set to custom value if enablePrivateNetworking is true.')
@secure()
//param vmAdminPassword string = newGuid()
param vmAdminPassword string?

@description('Optional. Size of the Jumpbox Virtual Machine when created. Set to custom value if enablePrivateNetworking is true.')
param vmSize string?

@description('Optional. Enable purge protection for the Key Vault')
param enablePurgeProtection bool = false

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
    tags: {
      ...tags
      TemplateName: 'Container Migration'
      Type: enablePrivateNetworking ? 'WAF' : 'Non-WAF'
      CreatedBy: createdBy
    }
  }
}

// Replica regions list based on article in [Azure regions list](https://learn.microsoft.com/azure/reliability/regions-list) and [Enhance resilience by replicating your Log Analytics workspace across regions](https://learn.microsoft.com/azure/azure-monitor/logs/workspace-replication#supported-regions) for supported regions for Log Analytics Workspace.
var replicaRegionPairs = {
  australiaeast: 'australiasoutheast'
  centralus: 'westus'
  eastasia: 'japaneast'
  eastus: 'centralus'
  eastus2: 'centralus'
  japaneast: 'eastasia'
  northeurope: 'westeurope'
  southeastasia: 'eastasia'
  uksouth: 'westeurope'
  westeurope: 'northeurope'
}
var replicaLocation = replicaRegionPairs[resourceGroup().location]

// ========== User Assigned Identity ========== //
// WAF best practices for identity and access management: https://learn.microsoft.com/en-us/azure/well-architected/security/identity-access
var userAssignedIdentityResourceName = 'id-${resourcesName}'
module appIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.1' = {
  name: take('avm.res.managed-identity.user-assigned-identity.${userAssignedIdentityResourceName}', 64)
  params: {
    name: userAssignedIdentityResourceName
    location: solutionLocation
    tags: tags
    enableTelemetry: enableTelemetry
  }
}

// ========== Network Module ========== //
module network 'modules/network.bicep' = if (enablePrivateNetworking) {
  name: take('network-${resourcesName}-deployment', 64)
  params: {
    resourcesName: resourcesName
    // logAnalyticsWorkSpaceResourceId: logAnalyticsWorkspace.outputs.resourceId
    logAnalyticsWorkSpaceResourceId: logAnalyticsWorkspaceResourceId
    vmAdminUsername: vmAdminUsername ?? 'JumpboxAdminUser'
    vmAdminPassword: vmAdminPassword ?? 'JumpboxAdminP@ssw0rd1234!'
    vmSize: vmSize ??  'Standard_DS2_v2' // Default VM size 
    location: solutionLocation
    tags: allTags
    enableTelemetry: enableTelemetry
  }
}

// ========== Log Analytics Workspace ========== //
// WAF best practices for Log Analytics: https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-log-analytics
// WAF PSRules for Log Analytics: https://azure.github.io/PSRule.Rules.Azure/en/rules/resource/#azure-monitor-logs
var logAnalyticsWorkspaceResourceName = 'log-${resourcesName}'
module logAnalyticsWorkspace 'br/public:avm/res/operational-insights/workspace:0.12.0' = if (enableMonitoring || enablePrivateNetworking) {
  name: take('avm.res.operational-insights.workspace.${logAnalyticsWorkspaceResourceName}', 64)
  params: {
    name: logAnalyticsWorkspaceResourceName
    location: solutionLocation
    skuName: 'PerGB2018'
    dataRetention: 30
    diagnosticSettings: [{ useThisWorkspace: true }]
    tags: allTags
    enableTelemetry: enableTelemetry
    features: { enableLogAccessUsingOnlyResourcePermissions: true }
    // WAF aligned configuration for Redundancy
    dailyQuotaGb: enableRedundancy ? 10 : null //WAF recommendation: 10 GB per day is a good starting point for most workloads
    replication: enableRedundancy
      ? {
          enabled: true
          location: replicaLocation
        }
      : null
    // WAF aligned configuration for Private Networking
    publicNetworkAccessForIngestion: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    publicNetworkAccessForQuery: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    dataSources: enablePrivateNetworking
      ? [
          {
            tags: tags
            eventLogName: 'Application'
            eventTypes: [
              {
                eventType: 'Error'
              }
              {
                eventType: 'Warning'
              }
              {
                eventType: 'Information'
              }
            ]
            kind: 'WindowsEvent'
            name: 'applicationEvent'
          }
          {
            counterName: '% Processor Time'
            instanceName: '*'
            intervalSeconds: 60
            kind: 'WindowsPerformanceCounter'
            name: 'windowsPerfCounter1'
            objectName: 'Processor'
          }
          {
            kind: 'IISLogs'
            name: 'sampleIISLog1'
            state: 'OnPremiseEnabled'
          }
        ]
      : null
  }
}

// ========== Application Insights ========== //
// WAF best practices for Application Insights: https://learn.microsoft.com/en-us/azure/well-architected/service-guides/application-insights
// WAF PSRules for  Application Insights: https://azure.github.io/PSRule.Rules.Azure/en/rules/resource/#application-insights
var applicationInsightsResourceName = 'appi-${resourcesName}'
module applicationInsights 'br/public:avm/res/insights/component:0.6.0' = if (enableMonitoring) {
  name: take('avm.res.insights.component.${applicationInsightsResourceName}', 64)
  #disable-next-line no-unnecessary-dependson
  dependsOn: [logAnalyticsWorkspace]
  params: {
    name: applicationInsightsResourceName
    location: solutionLocation
    tags: allTags
    enableTelemetry: enableTelemetry
    retentionInDays: 365
    kind: 'web'
    disableIpMasking: false
    flowType: 'Bluefield'
    // WAF aligned configuration for Monitoring
    workspaceResourceId: enableMonitoring ? logAnalyticsWorkspaceResourceId : ''
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
  }
}

var processBlobContainerName = 'processes'
var processQueueName = 'processes-queue'

// ========== Private DNS Zones ========== //
var privateDnsZones = [
  'privatelink.cognitiveservices.azure.com'
  'privatelink.openai.azure.com'
  'privatelink.services.ai.azure.com'
  'privatelink.azurewebsites.net'
  'privatelink.blob.${environment().suffixes.storage}'
  'privatelink.queue.${environment().suffixes.storage}'
  'privatelink.file.${environment().suffixes.storage}'
  'privatelink.documents.azure.com'
  'privatelink.vaultcore.azure.net'
  'privatelink${environment().suffixes.sqlServerHostname}'
  'privatelink.search.windows.net'
  'privatelink.azconfig.io'
]

// DNS Zone Index Constants
var dnsZoneIndex = {
  cognitiveServices: 0
  openAI: 1
  aiServices: 2
  appService: 3
  storageBlob: 4
  storageQueue: 5
  storageFile: 6
  cosmosDB: 7
  keyVault: 8
  sqlServer: 9
  searchService: 10
  appConfig: 11
}

// List of DNS zone indices that correspond to AI-related services.
var aiRelatedDnsZoneIndices = [
  dnsZoneIndex.cognitiveServices
  dnsZoneIndex.openAI
  dnsZoneIndex.aiServices
]

// ===================================================
// DEPLOY PRIVATE DNS ZONES
// - Deploys all zones if no existing Foundry project is used
// - Excludes AI-related zones when using with an existing Foundry project
// ===================================================
@batchSize(5)
module avmPrivateDnsZones 'br/public:avm/res/network/private-dns-zone:0.7.1' = [
  for (zone, i) in privateDnsZones: if (enablePrivateNetworking && (empty(existingFoundryProjectResourceId) || !contains(aiRelatedDnsZoneIndices, i))) {
    name: 'dns-zone-${i}'
    params: {
      name: zone
      tags: tags
      enableTelemetry: enableTelemetry
      virtualNetworkLinks: [
        {
          name: take('vnetlink-${network!.outputs.vnetName}-${split(zone, '.')[1]}', 80)
          virtualNetworkResourceId: network!.outputs.vnetResourceId
        }
      ]
    }
  }
]

// ========== AVM WAF ========== //
// ========== Storage account module ========== //
var storageAccountName = 'st${resourcesName}' // Storage account name must be between 3 and 24 characters in length and use numbers and lower-case letters only.
module storageAccount 'br/public:avm/res/storage/storage-account:0.20.0' = {
  name: take('avm.res.storage.storage-account.${storageAccountName}', 64)
  params: {
    name: storageAccountName
    location: solutionLocation
    managedIdentities: { systemAssigned: true }
    minimumTlsVersion: 'TLS1_2'
    enableTelemetry: enableTelemetry
    tags: allTags
    accessTier: 'Hot'
    supportsHttpsTrafficOnly: true
    roleAssignments: [
      {
        roleDefinitionIdOrName: 'Storage Blob Data Contributor'
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: 'Storage Queue Data Contributor'
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
    ]
    // WAF aligned networking
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: enablePrivateNetworking ? 'Deny' : 'Allow'
    }
    allowBlobPublicAccess: enablePrivateNetworking ? true : false
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    // Private endpoints for blob and queue
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: storageAccountName
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'storage-dns-zone-group-blob'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.storageBlob]!.outputs.resourceId
                }
              ]
            }
            subnetResourceId: network!.outputs.subnetPrivateEndpointsResourceId
            service: 'blob'
          }
          {
            name: 'pep-queue-${resourcesName}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'storage-dns-zone-group-queue'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.storageQueue]!.outputs.resourceId
                }
              ]
            }
            subnetResourceId: network!.outputs.subnetPrivateEndpointsResourceId
            service: 'queue'
          }
        ]
      : []
    blobServices: {
      corsRules: []
      deleteRetentionPolicyEnabled: false
      containers: [
        {
          name: 'data'
          publicAccess: 'None'
          denyEncryptionScopeOverride: false
          defaultEncryptionScope: '$account-encryption-key'
        }
      ]
    }
    queueServices: {
      deleteRetentionPolicyEnabled: true
      deleteRetentionPolicyDays: 7
      queues: [
        for queue in ([processQueueName, '${processQueueName}-dead-letter'] ?? []): {
          name: queue
        }
      ]
    }
  }
  dependsOn: [keyvault]
}



// module storageAccount 'modules/storageAccount.bicep' = {
//   name: take('module.storageAccount.${resourcesName}', 64)
//   #disable-next-line no-unnecessary-dependson
//   dependsOn: [logAnalyticsWorkspace]
//   params: {
//     name: take('sa${resourcesName}', 24)
//     location: solutionLocation
//     skuName: enableRedundancy ? 'Standard_GZRS' : 'Standard_LRS'
//     // TODO - private networking
//     // privateEndpointSubnetResourceId: privateEndpointSubnetResourceId
//     // blobPrivateDnsZoneResourceId: blobPrivateDnsZoneResourceId
//     // queuePrivateDnsZoneResourceId: queuePrivateDnsZoneResourceId
//     containers: [processBlobContainerName]
//     queues: [processQueueName, '${processQueueName}-dead-letter']
//     logAnalyticsWorkspaceResourceId: enableMonitoring ? logAnalyticsWorkspace!.outputs!.resourceId : ''
//     roleAssignments: [
//       {
//         roleDefinitionIdOrName: 'Storage Blob Data Contributor'
//         principalId: appIdentity.properties.principalId
//         principalType: 'ServicePrincipal'
//       }
//       {
//         roleDefinitionIdOrName: 'Storage Queue Data Contributor'
//         principalId: appIdentity.properties.principalId
//         principalType: 'ServicePrincipal'
//       }
//     ]
//     enableTelemetry: enableTelemetry
//     tags: allTags
//   }
// }


//========== AVM WAF ========== //
//========== Cosmos DB module ========== //

var sqlServerFqdn = 'sql-${resourcesName}.database.windows.net'
var sqlDbName = 'sqldb-${resourcesName}'
@description('Optional. API version for the Azure OpenAI service.')
param azureOpenaiAPIVersion string = '2025-04-01-preview'

@minLength(1)
@description('Optional. Name of the Text Embedding model to deploy:')
@allowed([
  'text-embedding-ada-002'
])
param embeddingModel string = 'text-embedding-ada-002'

var azureSearchIndex = 'transcripts_index'


var cosmosDbResourceName = 'cosmos-${resourcesName}'
var cosmosDbDatabaseName = 'db_conversation_history'
var collectionName = 'conversations'

var cosmosDbZoneRedundantHaRegionPairs = {
  australiaeast: 'uksouth' //'southeastasia'
  centralus: 'eastus2'
  eastasia: 'southeastasia'
  eastus: 'centralus'
  eastus2: 'centralus'
  japaneast: 'australiaeast'
  northeurope: 'westeurope'
  southeastasia: 'eastasia'
  uksouth: 'westeurope'
  westeurope: 'northeurope'
}
var cosmosDbHaLocation = cosmosDbZoneRedundantHaRegionPairs[resourceGroup().location]

import { roleAssignmentType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@description('Optional. Array of role assignments to create.')
param roleAssignments roleAssignmentType[]?

var cosmosDatabaseName = 'migration_db'
var processCosmosContainerName = 'processes'
var agentTelemetryCosmosContainerName = 'agent_telemetry'

resource sqlContributorRoleDefinition 'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions@2024-11-15' existing = {
  name: '${cosmosDbResourceName}/00000000-0000-0000-0000-000000000002'
}

// ==========Key Vault Module ========== //
var keyVaultName = 'KV-${resourcesName}' // Key Vault name must be between 3 and 24 characters in length and use numbers and lower-case letters only.
module keyvault 'br/public:avm/res/key-vault/vault:0.12.1' = {
  name: take('avm.res.key-vault.vault.${keyVaultName}', 64)
  params: {
    name: keyVaultName
    location: solutionLocation
    tags: tags
    sku: 'standard'
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
    enableVaultForDeployment: true
    enableVaultForDiskEncryption: true
    enableVaultForTemplateDeployment: true
    enableRbacAuthorization: true
    enableSoftDelete: true
    enablePurgeProtection: enablePurgeProtection
    softDeleteRetentionInDays: 7
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : []
    // WAF aligned configuration for Private Networking
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-${keyVaultName}'
            customNetworkInterfaceName: 'nic-${keyVaultName}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                { privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.keyVault]!.outputs.resourceId }
              ]
            }
            service: 'vault'
            subnetResourceId: network!.outputs.subnetPrivateEndpointsResourceId
          }
        ]
      : []
    // WAF aligned configuration for Role-based Access Control
    roleAssignments: [
      {
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: 'Key Vault Administrator'
      }
    ]
    secrets: [
        {
          name: 'SQLDB-SERVER'
          value: sqlServerFqdn
        }
        {
          name: 'SQLDB-DATABASE'
          value: sqlDbName
        }
        {
          name: 'AZURE-OPENAI-PREVIEW-API-VERSION'
          value: azureOpenaiAPIVersion
        }
        // {
        //   name: 'AZURE-OPENAI-ENDPOINT'
        //   value: aiFoundry.outputs.endpoints['OpenAI Language Model Instance API']
        // }
        {
          name: 'AZURE-OPENAI-EMBEDDING-MODEL'
          value: embeddingModel
        }
        {
          name: 'AZURE-SEARCH-INDEX'
          value: azureSearchIndex
        }
        // {
        //   name: 'AZURE-SEARCH-ENDPOINT'
        //   value: 'https://${aiSearchName}.search.windows.net'
        // }
    ]
    enableTelemetry: enableTelemetry
  }
}

module cosmosDb 'br/public:avm/res/document-db/database-account:0.15.0' = {
  name: take('avm.res.document-db.database-account.${cosmosDbResourceName}', 64)
  params: {
    name: cosmosDbResourceName
    location: cosmosLocation
    tags: tags
    enableTelemetry: enableTelemetry

    sqlDatabases: [
      {
        name: cosmosDatabaseName
        containers: [
          {
            name: processCosmosContainerName
            paths: [
              '/_partitionKey'
            ]
          }
          {
            name: agentTelemetryCosmosContainerName
            paths: [
              '/_partitionKey'
            ]
          }
          {
            name: 'files'
            paths: [
              '/_partitionKey'
            ]
          }
            {
              name: 'process_statuses'
              paths: [
                '/_partitionKey'
              ]
            }
        ]
      }
    ]

    diagnosticSettings: enableMonitoring ? [
      {
        workspaceResourceId: logAnalyticsWorkspaceResourceId
      }
    ] : null

    networkRestrictions: {
      networkAclBypass: 'None'
      publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    }

    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-${cosmosDbResourceName}'
            customNetworkInterfaceName: 'nic-${cosmosDbResourceName}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                { privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.cosmosDB]!.outputs.resourceId }
              ]
            }
            service: 'Sql'
            subnetResourceId: network!.outputs.subnetPrivateEndpointsResourceId
          }
        ]
      : []

    zoneRedundant: enableRedundancy ? true : false
    capabilitiesToAdd: enableRedundancy ? null : [
      'EnableServerless'
    ]
    automaticFailover: enableRedundancy ? true : false
    failoverLocations: enableRedundancy ? [
      {
        failoverPriority: 0
        isZoneRedundant: true
        locationName: solutionLocation
      }
      {
        failoverPriority: 1
        isZoneRedundant: true
        locationName: cosmosDbHaLocation
      }
    ] : [
      {
        locationName: solutionLocation
        failoverPriority: 0
        isZoneRedundant: enableRedundancy
      }
    ]
    dataPlaneRoleDefinitions: [
      {
        // Cosmos DB Built-in Data Contributor: https://docs.azure.cn/en-us/cosmos-db/nosql/security/reference-data-plane-roles#cosmos-db-built-in-data-contributor
        roleName: 'Cosmos DB SQL Data Contributor'
        dataActions: [
          'Microsoft.DocumentDB/databaseAccounts/readMetadata'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/*'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/*'
        ]
        assignments: [
          { principalId: appIdentity.outputs.principalId }
        ]
      }
    ]
    // Grant data plane access to the managed identity
    dataPlaneRoleAssignments: [
      {
        principalId: appIdentity.outputs.principalId
        roleDefinitionId: sqlContributorRoleDefinition.id
      }
    ]
  }
  dependsOn: [keyvault, storageAccount]
}

// module cosmosDb 'br/public:avm/res/document-db/database-account:0.16.0' = {
//   name: take('avm.res.document-db.account.${cosmosDbResourceName}', 64)
//   params: {
//     name: cosmosDbResourceName
//     enableAnalyticalStorage: true
//     location: cosmosLocation
//     minimumTlsVersion: 'Tls12'
//     defaultConsistencyLevel: 'Session'
//     networkRestrictions: {
//       networkAclBypass: 'None'
//       publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
//       //ipRules: []
//       //virtualNetworkRules: []
//     }
//     zoneRedundant: enableRedundancy ? true : false
//     automaticFailover: enableRedundancy ? true : false
//     failoverLocations: !empty(secondaryLocation)
//       ? [
//           {
//             failoverPriority: 0
//             isZoneRedundant: enableRedundancy
//             locationName: location
//           }
//           {
//             failoverPriority: 1
//             isZoneRedundant: enableRedundancy
//             locationName: secondaryLocation!
//           }
//         ]
//       : []
//     enableMultipleWriteLocations: !empty(secondaryLocation)
//     backupPolicyType: !empty(secondaryLocation) ? 'Periodic' : 'Continuous'
//     backupStorageRedundancy: enableRedundancy ? 'Zone' : 'Local'
//     disableKeyBasedMetadataWriteAccess: false
//     disableLocalAuthentication: true
//     diagnosticSettings: !empty(logAnalyticsWorkspaceResourceId)? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }]: []
//     // privateEndpoints: enablePrivateNetworking
//     //   ? [
//     //       {
//     //         privateDnsZoneGroup: {
//     //           privateDnsZoneGroupConfigs: [
//     //             {
//     //               privateDnsZoneResourceId: sqlPrivateDnsZoneResourceId!
//     //             }
//     //           ]
//     //         }
//     //         service: 'Sql'
//     //         subnetResourceId: privateEndpointSubnetResourceId!
//     //       }
//     //     ]
//     //   : []
//     sqlDatabases: [
//       {
//         containers: [
//           {
//             indexingPolicy: {
//               automatic: true
//             }
//             name: processCosmosContainerName
//             paths: [
//               '/_partitionKey'
//             ]
//           }
//           {
//             indexingPolicy: {
//               automatic: true
//             }
//             name: agentTelemetryCosmosContainerName
//             paths: [
//               '/_partitionKey'
//             ]
//           }
//           {
//             indexingPolicy: {
//               automatic: true
//             }
//             name: 'files'
//             paths: [
//               '/_partitionKey'
//             ]
//           }
//           {
//             indexingPolicy: {
//               automatic: true
//             }
//             name: 'process_statuses'
//             paths: [
//               '/_partitionKey'
//             ]
//           }
//         ]
//         name: cosmosDatabaseName
//       }
//     ]
//     dataPlaneRoleAssignments: !empty(appIdentity.properties.principalId) ? [
//       {
//         principalId: appIdentity.properties.principalId!
//         roleDefinitionId: sqlContributorRoleDefinition.id
//       }
//     ] : []
//     roleAssignments: roleAssignments
//     tags: allTags
//     enableTelemetry: enableTelemetry
//   }
// }

// module cosmosDb 'modules/cosmosDb.bicep' = {
//   name: take('module.cosmosdb.${resourcesName}', 64)
//   #disable-next-line no-unnecessary-dependson
//   dependsOn: [logAnalyticsWorkspace]
//   params: {
//     name: take('cosmos-${resourcesName}', 44)
//     location: solutionLocation
//     zoneRedundant: enableRedundancy
//     secondaryLocation: enableRedundancy && !empty(secondaryLocation) ? secondaryLocation : ''
//     databaseName: cosmosDatabaseName
//     containers: [
//       processCosmosContainerName
//       agentTelemetryCosmosContainerName
//       'files'
//       'process_statuses'
//     ]
//     // TODO - private networking
//     // privateEndpointSubnetResourceId: privateEndpointSubnetResourceId
//     // sqlPrivateDnsZoneResourceId: sqlPrivateDnsZoneResourceId
//     dataAccessIdentityPrincipalId: appIdentity.properties.principalId
//     logAnalyticsWorkspaceResourceId: enableMonitoring ? logAnalyticsWorkspace!.outputs!.resourceId : ''
//     enableTelemetry: enableTelemetry
//     tags: allTags
//   }
// }

var aiModelDeploymentName = aiModelName

module aiFoundry 'br/public:avm/ptn/ai-ml/ai-foundry:0.4.0' = {
  name: take('avm.ptn.ai-ml.ai-foundry.${resourcesName}', 64)
  params: {
    #disable-next-line BCP334
    baseName: take(resourcesName, 12)
    baseUniqueName: null
    location: azureAiServiceLocation
    aiFoundryConfiguration: {
      allowProjectManagement: true
      roleAssignments: [
        {
          principalId: appIdentity.outputs.principalId
          principalType: 'ServicePrincipal'
          roleDefinitionIdOrName: 'Cognitive Services OpenAI Contributor'
        }
        {
          principalId: appIdentity.outputs.principalId
          principalType: 'ServicePrincipal'
          roleDefinitionIdOrName: '64702f94-c441-49e6-a78b-ef80e0188fee' // Azure AI Developer
        }
        {
          principalId: appIdentity.outputs.principalId
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
    location: solutionLocation
    name: 'appcs-${resourcesName}'
    disableLocalAuth: false // needed to allow setting app config key values from this module
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
        value: 'https://${storageAccountName}.blob.${environment().suffixes.storage}'
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
        value: 'https://${storageAccountName}.queue.${environment().suffixes.storage}'
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
        privateEndpoints: enablePrivateNetworking ? [
      {
        name: 'pep-appcs-${resourcesName}'
        subnetResourceId: network!.outputs.subnetPrivateEndpointsResourceId
        privateDnsZoneGroup: {
          privateDnsZoneGroupConfigs: [
            {
              privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.appConfig]!.outputs.resourceId
            }
          ]
        }
      }
    ] : []
    roleAssignments: [
      {
        principalId: appIdentity.outputs.principalId
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
  dependsOn: [logAnalyticsWorkspace, applicationInsights]
  params: {
    name: containerAppsEnvironmentName
    infrastructureResourceGroupName: '${resourceGroup().name}-ME-${containerAppsEnvironmentName}'
    location: solutionLocation
    publicNetworkAccess: 'Enabled'
    zoneRedundant: enableRedundancy && enablePrivateNetworking
    //infrastructureSubnetResourceId: enablePrivateNetworking ? network!.outputs.subnetContainerAppsInfraResourceId : null
    // workloadProfiles: enablePrivateNetworking ? [
    //   {
    //     name: 'Consumption'
    //     workloadProfileType: 'Consumption'
    //   }
    // ] : []
    managedIdentities: {
      userAssignedResourceIds: [
        appIdentity.outputs.resourceId
      ]
    }
    appInsightsConnectionString: enableMonitoring ? applicationInsights!.outputs.connectionString : null
    appLogsConfiguration: enableMonitoring ? {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace!.outputs.logAnalyticsWorkspaceId
        sharedKey: logAnalyticsWorkspace!.outputs!.primarySharedKey
      }
    } : {}
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
    location: solutionLocation
    environmentResourceId: containerAppsEnvironment.outputs.resourceId
    managedIdentities: {
      userAssignedResourceIds: [
        appIdentity.outputs.resourceId
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
              value: appIdentity.outputs.clientId
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
    location: solutionLocation
    environmentResourceId: containerAppsEnvironment.outputs.resourceId
    managedIdentities: {
      userAssignedResourceIds: [
        appIdentity.outputs.resourceId
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
    location: solutionLocation
    environmentResourceId: containerAppsEnvironment.outputs.resourceId
    managedIdentities: {
      userAssignedResourceIds: [
        appIdentity.outputs.resourceId
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
              value: appIdentity.outputs.clientId
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
