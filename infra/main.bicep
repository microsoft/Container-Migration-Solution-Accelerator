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
@description('Required. Azure region for container apps, storage, and other services. Choose a region close to your users.')
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
  azd: {
    type: 'location'
    usageName: [
      'OpenAI.GlobalStandard.gpt-5.1, 500'
    ]
  }
})
@description('Required. Azure region for AI services (OpenAI/AI Foundry). Must be a region that supports gpt-5.1 model deployment.')
param azureAiServiceLocation string



@description('Optional. [Deprecated] The endpoint (excluding https://) of an existing container registry. Retained only for backward compatibility with existing parameter files/pipelines; each deployment now provisions its own dedicated Azure Container Registry and no longer depends on a shared/public registry.')
#disable-next-line no-unused-params
param containerRegistryEndpoint string = ''

@description('Optional. The image tag to use for container images. Defaults to "latest_v2".')
param imageTag string = 'latest_v2'

@description('''Optional. Placeholder container image used to initially provision the container apps.
The dedicated Azure Container Registry is empty right after infrastructure provisioning, so a public image is used as the default allowed image until the post-deployment script (scripts/deploy_container_images.*) builds and pushes the deployment-specific images and updates the apps. Defaults to the Azure Container Apps quickstart image.''')
param placeholderContainerImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

@minLength(1)
@allowed(['Standard', 'GlobalStandard'])
@description('Optional. Model deployment type. Defaults to GlobalStandard.')
param deploymentType string = 'GlobalStandard'

@minLength(1)
@description('Optional. Name of the AI model to deploy. Recommend using gpt-5.1. Defaults to gpt-5.1.')
param gptModelName string = 'gpt-5.1'

@minLength(1)
@description('Optional. Version of AI model. Review available version numbers per model before setting. Defaults to 2025-11-13.')
param gptModelVersion string = '2025-11-13'

@description('Optional. GPT model deployment token capacity. Lower this if initial provisioning fails due to capacity. Defaults to 500K tokens per minute to improve regional success rate.')
param gptDeploymentCapacity int = 500

@minLength(1)
@description('Optional. Name of the embedding model to deploy. Defaults to text-embedding-3-large.')
param aiEmbeddingModelName string = 'text-embedding-3-large'

@description('Optional. Version of the embedding model. Defaults to 1.')
param aiEmbeddingModelVersion string = '1'

@minLength(1)
@allowed(['Standard', 'GlobalStandard'])
@description('Optional. Embedding model deployment type. Defaults to GlobalStandard.')
param aiEmbeddingDeploymentType string = 'GlobalStandard'

@description('Optional. Embedding model deployment token capacity. Defaults to 500.')
param aiEmbeddingModelCapacity int = 500

@description('Optional. The tags to apply to all deployed Azure resources.')
param tags resourceInput<'Microsoft.Resources/resourceGroups@2025-04-01'>.tags = {}

@description('Optional. Enable redundancy for applicable resources. Defaults to false.')
param enableRedundancy bool = false

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

@description('Optional. Override for the CreatedBy tag. If not provided, will auto-detect from deployment context.')
param createdBy string = ''

// Get the current deployer's information for local debugging permissions
var deployerInfo = deployer()
var deployingUserPrincipalId = deployerInfo.objectId
var deployingUserType = contains(deployerInfo, 'userPrincipalName') ? 'User' : 'ServicePrincipal'

// Extract human-readable identity name for CreatedBy tag
var deployerIdentityName = !empty(createdBy) 
  ? createdBy 
  : deployerInfo.?userPrincipalName != null
    ? split(deployerInfo.userPrincipalName, '@')[0]
    : 'Identity-${deployerInfo.objectId}'

// Output for pre-deployment validation - shows what CreatedBy will be
output previewCreatedByTag string = deployerIdentityName
output previewDeployerInfo object = {
  identityName: deployerIdentityName
  objectId: deployingUserPrincipalId
  type: deployingUserType
}

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

// Extracts subscription, resource group, and workspace name from the resource ID when using an existing Log Analytics workspace
var useExistingLogAnalytics = !empty(existingLogAnalyticsWorkspaceId)
var existingLawSubscription = useExistingLogAnalytics ? split(existingLogAnalyticsWorkspaceId, '/')[2] : ''
var existingLawResourceGroup = useExistingLogAnalytics ? split(existingLogAnalyticsWorkspaceId, '/')[4] : ''
var existingLawName = useExistingLogAnalytics ? split(existingLogAnalyticsWorkspaceId, '/')[8] : ''

resource existingLogAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2020-08-01' existing = if (useExistingLogAnalytics) {
  name: existingLawName
  scope: resourceGroup(existingLawSubscription, existingLawResourceGroup)
}

var logAnalyticsWorkspaceResourceId = useExistingLogAnalytics
  ? existingLogAnalyticsWorkspaceId
  : logAnalyticsWorkspace!.outputs.resourceId

var solutionSuffix = toLower(trim(replace(
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

var existingTags = resourceGroup().tags ?? {}

resource resourceGroupTags 'Microsoft.Resources/tags@2021-04-01' = {
  name: 'default'
  properties: {
    tags: union(
      existingTags,
      tags,
      {
        TemplateName: 'Container Migration'
        Type: enablePrivateNetworking ? 'WAF' : 'Non-WAF'
        CreatedBy: deployerIdentityName
      }
    )
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
  westus3: 'eastus'
}
var replicaLocation = replicaRegionPairs[resourceGroup().location]

// ========== User Assigned Identity ========== //
// WAF best practices for identity and access management: https://learn.microsoft.com/en-us/azure/well-architected/security/identity-access
var userAssignedIdentityResourceName = 'id-${solutionSuffix}'
module appIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.1' = {
  name: take('avm.res.managed-identity.user-assigned-identity.${userAssignedIdentityResourceName}', 64)
  params: {
    name: userAssignedIdentityResourceName
    location: solutionLocation
    tags: allTags
    enableTelemetry: enableTelemetry
  }
}

// ========== Dedicated Azure Container Registry ========== //
// Each deployment provisions its own ACR instead of relying on a shared/public
// registry with anonymous pull. Images are pulled using identity-based
// authentication (AcrPull role granted to the application managed identity).
var containerRegistryName = take('cr${solutionSuffix}', 50)
module containerRegistry './modules/containerRegistry.bicep' = {
  name: take('module.container-registry.${solutionSuffix}', 64)
  params: {
    name: containerRegistryName
    location: solutionLocation
    tags: allTags
    // Premium SKU in WAF/private-networking mode (supports higher throughput and
    // future private endpoints). Public network access is kept Enabled in both
    // modes so remote `az acr build` (ACR Tasks) and managed-identity pulls work;
    // AzureServices bypass lets trusted ACR Tasks reach the registry.
    sku: enablePrivateNetworking ? 'Premium' : 'Standard'
    publicNetworkAccess: 'Enabled'
    networkRuleBypassOptions: 'AzureServices'
    // Application managed identity gets AcrPull for identity-based image pulls.
    acrPullPrincipalIds: [
      appIdentity.outputs.principalId
    ]
    // Deployer gets a registry-scoped Contributor role so it can run remote
    // builds (az acr build) and push images from the post-deployment script.
    buildPrincipalId: deployingUserPrincipalId
    buildPrincipalType: deployingUserType
  }
}

// ========== Log Analytics Workspace ========== //
// WAF best practices for Log Analytics: https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-log-analytics
// WAF PSRules for Log Analytics: https://azure.github.io/PSRule.Rules.Azure/en/rules/resource/#azure-monitor-logs
var logAnalyticsWorkspaceResourceName = 'log-${solutionSuffix}'
module logAnalyticsWorkspace 'br/public:avm/res/operational-insights/workspace:0.12.0' = if ((enableMonitoring || enablePrivateNetworking) && !useExistingLogAnalytics) {
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
            tags: allTags
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
var applicationInsightsResourceName = 'appi-${solutionSuffix}'
module applicationInsights 'br/public:avm/res/insights/component:0.6.0' = if (enableMonitoring) {
  name: take('avm.res.insights.component.${applicationInsightsResourceName}', 64)
  #disable-next-line no-unnecessary-dependson
  //dependsOn: [logAnalyticsWorkspace]
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

// ========== Virtual Network ========== //
module virtualNetwork './modules/virtualNetwork.bicep' = if (enablePrivateNetworking) {
  name: take('module.virtual-network.${solutionSuffix}', 64)
  params: {
    name: 'vnet-${solutionSuffix}'
    addressPrefixes: ['10.0.0.0/20']
    location: location
    tags: allTags
    logAnalyticsWorkspaceId: enableMonitoring ? logAnalyticsWorkspaceResourceId : ''
    resourceSuffix: solutionSuffix
    enableTelemetry: enableTelemetry
  }
}

// Azure Bastion Host
var bastionHostName = 'bas-${solutionSuffix}' // Bastion host name must be between 3 and 15 characters in length and use numbers and lower-case letters only.
module bastionHost 'br/public:avm/res/network/bastion-host:0.6.1' = if (enablePrivateNetworking) {
  name: take('avm.res.network.bastion-host.${bastionHostName}', 64)
  params: {
    name: bastionHostName
    skuName: 'Standard'
    location: location
    virtualNetworkResourceId: virtualNetwork!.outputs.resourceId
    diagnosticSettings: enableMonitoring
      ? [
          {
            name: 'bastionDiagnostics'
            workspaceResourceId: logAnalyticsWorkspaceResourceId
            logCategoriesAndGroups: [
              {
                categoryGroup: 'allLogs'
                enabled: true
              }
            ]
          }
        ]
      : null
    tags: allTags
    enableTelemetry: enableTelemetry
    publicIPAddressObject: {
      name: 'pip-${bastionHostName}'
      zones: []
    }
  }
}
// Jumpbox Virtual Machine
var jumpboxVmName = take('vm-jumpbox-${solutionSuffix}', 15)
module jumpboxVM 'br/public:avm/res/compute/virtual-machine:0.15.0' = if (enablePrivateNetworking) {
  name: take('avm.res.compute.virtual-machine.${jumpboxVmName}', 64)
  params: {
    name: take(jumpboxVmName, 15) // Shorten VM name to 15 characters to avoid Azure limits
    vmSize: vmSize ?? 'Standard_D2s_v5'
    location: location
    adminUsername: vmAdminUsername ?? 'JumpboxAdminUser'
    adminPassword: vmAdminPassword ?? 'JumpboxAdminP@ssw0rd1234!'
    tags: allTags
    zone: 0
    // SFI: enable system-assigned managed identity on the jumpbox VM. Required so
    // the Azure Monitor Agent can authenticate to the Log Analytics workspace and
    // honor the SecurityAuditEvents data collection rule association.
    managedIdentities: { systemAssigned: true }
    imageReference: {
      offer: 'WindowsServer'
      publisher: 'MicrosoftWindowsServer'
      sku: '2019-datacenter'
      version: 'latest'
    }
    osType: 'Windows'
    osDisk: {
      name: 'osdisk-${jumpboxVmName}'
      managedDisk: {
        storageAccountType: 'Standard_LRS'
      }
    }
    encryptionAtHost: false // Some Azure subscriptions do not support encryption at host
    nicConfigurations: [
      {
        name: 'nic-${jumpboxVmName}'
        ipConfigurations: [
          {
            name: 'ipconfig1'
            subnetResourceId: virtualNetwork!.outputs.jumpboxSubnetResourceId
          }
        ]
        diagnosticSettings: enableMonitoring
          ? [
              {
                name: 'jumpboxDiagnostics'
                workspaceResourceId: logAnalyticsWorkspaceResourceId
                logCategoriesAndGroups: [
                  {
                    categoryGroup: 'allLogs'
                    enabled: true
                  }
                ]
                metricCategories: [
                  {
                    category: 'AllMetrics'
                    enabled: true
                  }
                ]
              }
            ]
          : null
      }
    ]
    enableTelemetry: enableTelemetry
    // SFI: associate the SecurityAuditEvents data collection rule with the
    // jumpbox VM via the Azure Monitor Agent extension. Routes Windows audit
    // success / audit failure events to Log Analytics. Gated on the same
    // (enablePrivateNetworking && enableMonitoring) expression as the DCR
    // module so the dereference of windowsVmDataCollectionRules!.outputs
    // stays safe even if the outer jumpbox VM gate ever changes.
    extensionMonitoringAgentConfig: (enablePrivateNetworking && enableMonitoring)
      ? {
          enabled: true
          tags: allTags
          dataCollectionRuleAssociations: [
            {
              name: 'send-${logAnalyticsWorkspaceResourceName}'
              dataCollectionRuleResourceId: windowsVmDataCollectionRules!.outputs.resourceId
            }
          ]
        }
      : null
  }
}

// SFI: data collection rule that captures Windows Security audit success and
// audit failure events from the jumpbox VM and routes them to Log Analytics
// via the Microsoft-Event stream. The xPath filter uses the Windows
// audit Keywords bitmask (0x30000000000000 = AuditSuccess|AuditFailure) and
// excludes EventID 4624 (successful logon) because it is extremely
// high-volume. Also collects a small set of Windows performance counters via
// Microsoft-Perf for the jumpbox so the same DCR provides basic VM health
// signal. The SecurityEvent / Perf tables are auto-provisioned by Azure
// Monitor on first ingestion via the DCR; no legacy OMSGallery/Security
// solution is needed.
var dataCollectionRulesResourceName = 'dcr-${solutionSuffix}'
var dataCollectionRulesLocation = useExistingLogAnalytics
  ? existingLogAnalyticsWorkspace!.location
  : logAnalyticsWorkspace!.outputs.location
var dcrLogAnalyticsDestinationName = 'la-${logAnalyticsWorkspaceResourceName}-destination'
module windowsVmDataCollectionRules 'br/public:avm/res/insights/data-collection-rule:0.11.0' = if (enablePrivateNetworking && enableMonitoring) {
  name: take('avm.res.insights.data-collection-rule.${dataCollectionRulesResourceName}', 64)
  params: {
    name: dataCollectionRulesResourceName
    tags: allTags
    enableTelemetry: enableTelemetry
    location: dataCollectionRulesLocation
    dataCollectionRuleProperties: {
      kind: 'Windows'
      dataSources: {
        windowsEventLogs: [
          {
            name: 'SecurityAuditEvents'
            streams: [
              'Microsoft-Event'
            ]
            xPathQueries: [
              'Security!*[System[(band(Keywords,13510798882111488)) and (EventID != 4624)]]'
            ]
          }
        ]
        performanceCounters: [
          {
            name: 'perfCounterDataSource60'
            streams: [
              'Microsoft-Perf'
            ]
            samplingFrequencyInSeconds: 60
            counterSpecifiers: [
              '\\Processor Information(_Total)\\% Processor Time'
              '\\Processor Information(_Total)\\% Privileged Time'
              '\\Processor Information(_Total)\\% User Time'
              '\\Processor Information(_Total)\\Processor Frequency'
              '\\System\\Processes'
              '\\Process(_Total)\\Thread Count'
              '\\Process(_Total)\\Handle Count'
              '\\System\\System Up Time'
              '\\System\\Context Switches/sec'
              '\\System\\Processor Queue Length'
              '\\Memory\\% Committed Bytes In Use'
              '\\Memory\\Available Bytes'
              '\\Memory\\Committed Bytes'
              '\\Memory\\Cache Bytes'
              '\\Memory\\Pool Paged Bytes'
              '\\Memory\\Pool Nonpaged Bytes'
              '\\Memory\\Pages/sec'
              '\\Memory\\Page Faults/sec'
              '\\Process(_Total)\\Working Set'
              '\\Process(_Total)\\Working Set - Private'
              '\\LogicalDisk(_Total)\\% Disk Time'
              '\\LogicalDisk(_Total)\\% Disk Read Time'
              '\\LogicalDisk(_Total)\\% Disk Write Time'
              '\\LogicalDisk(_Total)\\% Idle Time'
              '\\LogicalDisk(_Total)\\Disk Bytes/sec'
              '\\LogicalDisk(_Total)\\Disk Read Bytes/sec'
              '\\LogicalDisk(_Total)\\Disk Write Bytes/sec'
              '\\LogicalDisk(_Total)\\Disk Transfers/sec'
              '\\LogicalDisk(_Total)\\Disk Reads/sec'
              '\\LogicalDisk(_Total)\\Disk Writes/sec'
              '\\LogicalDisk(_Total)\\Avg. Disk sec/Transfer'
              '\\LogicalDisk(_Total)\\Avg. Disk sec/Read'
              '\\LogicalDisk(_Total)\\Avg. Disk sec/Write'
              '\\LogicalDisk(_Total)\\Avg. Disk Queue Length'
              '\\LogicalDisk(_Total)\\Avg. Disk Read Queue Length'
              '\\LogicalDisk(_Total)\\Avg. Disk Write Queue Length'
              '\\LogicalDisk(_Total)\\% Free Space'
              '\\LogicalDisk(_Total)\\Free Megabytes'
              '\\Network Interface(*)\\Bytes Total/sec'
              '\\Network Interface(*)\\Bytes Sent/sec'
              '\\Network Interface(*)\\Bytes Received/sec'
              '\\Network Interface(*)\\Packets/sec'
              '\\Network Interface(*)\\Packets Sent/sec'
              '\\Network Interface(*)\\Packets Received/sec'
              '\\Network Interface(*)\\Packets Outbound Errors'
              '\\Network Interface(*)\\Packets Received Errors'
            ]
          }
        ]
      }
      destinations: {
        logAnalytics: [
          {
            workspaceResourceId: logAnalyticsWorkspaceResourceId
            name: dcrLogAnalyticsDestinationName
          }
        ]
      }
      dataFlows: [
        {
          streams: [
            'Microsoft-Event'
          ]
          destinations: [
            dcrLogAnalyticsDestinationName
          ]
        }
        {
          streams: [
            'Microsoft-Perf'
          ]
          destinations: [
            dcrLogAnalyticsDestinationName
          ]
        }
      ]
    }
  }
}

var processBlobContainerName = 'processes'
var processQueueName = 'processes-queue'

// ========== Private DNS Zones ========== //
var privateDnsZones = [
  'privatelink.cognitiveservices.azure.com'
  'privatelink.openai.azure.com'
  'privatelink.services.ai.azure.com'
  'privatelink.documents.azure.com'
  'privatelink.blob.${environment().suffixes.storage}'
  'privatelink.queue.${environment().suffixes.storage}'
  'privatelink.azconfig.io'
]

// DNS Zone Index Constants
var dnsZoneIndex = {
  cognitiveServices: 0
  openAI: 1
  aiServices: 2
  cosmosDB: 3
  storageBlob: 4
  storageQueue: 5
  appConfig: 6
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
  for (zone, i) in privateDnsZones: if (enablePrivateNetworking && (empty(existingFoundryProjectResourceId) || !contains(
    aiRelatedDnsZoneIndices,
    i
  ))) {
    name: 'dns-zone-${i}'
    params: {
      name: zone
      tags: allTags
      enableTelemetry: enableTelemetry
      virtualNetworkLinks: [
        {
          name: take('vnetlink-${virtualNetwork!.outputs.name}-${split(zone, '.')[1]}', 80)
          virtualNetworkResourceId: virtualNetwork!.outputs.resourceId
        }
      ]
    }
  }
]

// ========== AVM WAF ========== //
// ========== Storage account module ========== //
var storageAccountName = 'st${solutionSuffix}' // Storage account name must be between 3 and 24 characters in length and use numbers and lower-case letters only.
module storageAccount 'br/public:avm/res/storage/storage-account:0.20.0' = {
  name: take('avm.res.storage.storage-account.${storageAccountName}', 64)
  params: {
    name: storageAccountName
    location: solutionLocation
    managedIdentities: { systemAssigned: true }
    minimumTlsVersion: 'TLS1_2'
    // SFI: enable infrastructure (double) encryption at rest
    requireInfrastructureEncryption: true
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
      // Add deployer permissions
      {
        roleDefinitionIdOrName: 'Storage Blob Data Contributor'
        principalId: deployingUserPrincipalId
        principalType: deployingUserType
      }
      {
        roleDefinitionIdOrName: 'Storage Queue Data Contributor'
        principalId: deployingUserPrincipalId
        principalType: deployingUserType
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
            name: 'pep-storage-${storageAccountName}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'storage-dns-zone-group-blob'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.storageBlob]!.outputs.resourceId
                }
              ]
            }
            subnetResourceId: virtualNetwork!.outputs.backendSubnetResourceId
            service: 'blob'
          }
          {
            name: 'pep-queue-${solutionSuffix}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'storage-dns-zone-group-queue'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.storageQueue]!.outputs.resourceId
                }
              ]
            }
            subnetResourceId: virtualNetwork!.outputs.backendSubnetResourceId
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
}

//========== AVM WAF ========== //
//========== Cosmos DB module ========== //
var cosmosDbResourceName = 'cosmos-${solutionSuffix}'
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
  westus3: 'eastus'
}
var cosmosDbHaLocation = cosmosDbZoneRedundantHaRegionPairs[resourceGroup().location]

var cosmosDatabaseName = 'migration_db'
var processCosmosContainerName = 'processes'
var agentTelemetryCosmosContainerName = 'agent_telemetry'
var processControlCosmosContainerName = 'processcontrol'
module cosmosDb 'br/public:avm/res/document-db/database-account:0.15.0' = {
  name: take('avm.res.document-db.database-account.${cosmosDbResourceName}', 64)
  params: {
    name: cosmosDbResourceName
    location: cosmosLocation
    tags: allTags
    enableTelemetry: enableTelemetry
    // SFI: enable system-assigned managed identity for Cosmos DB account
    managedIdentities: { systemAssigned: true }
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
            name: processControlCosmosContainerName
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

    diagnosticSettings: enableMonitoring
      ? [
          {
            workspaceResourceId: logAnalyticsWorkspaceResourceId
          }
        ]
      : null

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
            subnetResourceId: virtualNetwork!.outputs.backendSubnetResourceId
          }
        ]
      : []

    zoneRedundant: enableRedundancy ? true : false
    capabilitiesToAdd: enableRedundancy
      ? null
      : [
          'EnableServerless'
        ]
    automaticFailover: enableRedundancy ? true : false
    failoverLocations: enableRedundancy
      ? [
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
        ]
      : [
          {
            locationName: solutionLocation
            failoverPriority: 0
            isZoneRedundant: enableRedundancy
          }
        ]
    // Use built-in Cosmos DB roles for RBAC access
    roleAssignments: [
      {
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: 'DocumentDB Account Contributor'
      }
      // Add deployer for local debugging
      {
        principalId: deployingUserPrincipalId
        principalType: deployingUserType
        roleDefinitionIdOrName: 'DocumentDB Account Contributor'
      }
    ]
    // Create custom data plane role definition and assignment
    dataPlaneRoleDefinitions: [
      {
        roleName: 'CosmosDB Data Contributor Custom'
        dataActions: [
          'Microsoft.DocumentDB/databaseAccounts/readMetadata'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/executeQuery'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/readChangeFeed'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/*'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/*'
        ]
        assignments: [
          { principalId: appIdentity.outputs.principalId }
          // ADD THIS for local debugging support:
          { principalId: deployingUserPrincipalId }
        ]
      }
    ]
  }
  dependsOn: [storageAccount]
}

var aiModelDeploymentName = gptModelName

var useExistingAiFoundryAiProject = !empty(existingFoundryProjectResourceId)
var aiFoundryAiServicesResourceGroupName = useExistingAiFoundryAiProject
  ? split(existingFoundryProjectResourceId, '/')[4]
  : 'rg-${solutionSuffix}'
var aiFoundryAiServicesSubscriptionId = useExistingAiFoundryAiProject
  ? split(existingFoundryProjectResourceId, '/')[2]
  : subscription().id
var aiFoundryAiServicesResourceName = useExistingAiFoundryAiProject
  ? split(existingFoundryProjectResourceId, '/')[8]
  : 'aif-${solutionSuffix}'

var aiFoundryAiProjectResourceName = 'proj-${solutionSuffix}'
var aiFoundryAiProjectDescription = 'AI Foundry project for ${solutionName}'

resource existingAiFoundryAiServices 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = if (useExistingAiFoundryAiProject) {
  name: aiFoundryAiServicesResourceName
  scope: resourceGroup(aiFoundryAiServicesSubscriptionId, aiFoundryAiServicesResourceGroupName)
}

module existingAiFoundryAiServicesDeployments 'modules/ai-services-deployments.bicep' = if (useExistingAiFoundryAiProject) {
  name: take('module.ai-services-model-deployments.${existingAiFoundryAiServices.name}', 64)
  scope: resourceGroup(aiFoundryAiServicesSubscriptionId, aiFoundryAiServicesResourceGroupName)
  params: {
    name: aiFoundryAiServicesResourceName  // Fix: use variable instead of resource reference
    deployments: [
      {
        name: aiModelDeploymentName
        model: {
          format: 'OpenAI'
          name: gptModelName
          version: gptModelVersion
        }
        sku: {
          name: deploymentType
          capacity: gptDeploymentCapacity
        }
      }
      {
        name: aiEmbeddingModelName
        model: {
          format: 'OpenAI'
          name: aiEmbeddingModelName
          version: aiEmbeddingModelVersion
        }
        sku: {
          name: aiEmbeddingDeploymentType
          capacity: aiEmbeddingModelCapacity
        }
      }
    ]
    roleAssignments: [
      // Service Principal permissions
      {
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: 'Cognitive Services OpenAI Contributor'
      }
      {
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: '64702f94-c441-49e6-a78b-ef80e0188fee'
      }
      {
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
      }
      // Deployer permissions
      {
        principalId: deployingUserPrincipalId
        principalType: deployingUserType
        roleDefinitionIdOrName: 'Cognitive Services OpenAI Contributor'
      }
      {
        principalId: deployingUserPrincipalId
        principalType: deployingUserType
        roleDefinitionIdOrName: 'Cognitive Services User'
      }
    ]
  }
}

// ========== AI Foundry AI Services ========== //
module aiFoundryAiServices 'br/public:avm/res/cognitive-services/account:0.13.2' = if (!useExistingAiFoundryAiProject) {
  name: take('avm.res.cognitive-services.account.${aiFoundryAiServicesResourceName}', 64)
  params: {
    name: aiFoundryAiServicesResourceName
    location: empty(azureAiServiceLocation) ? location : azureAiServiceLocation
    tags: allTags
    sku: 'S0'
    kind: 'AIServices'
    disableLocalAuth: true
    allowProjectManagement: true
    customSubDomainName: aiFoundryAiServicesResourceName
    deployments: [
      {
        name: aiModelDeploymentName
        model: {
          format: 'OpenAI'
          name: gptModelName
          version: gptModelVersion
        }
        sku: {
          name: deploymentType
          capacity: gptDeploymentCapacity
        }
      }
      {
        name: aiEmbeddingModelName
        model: {
          format: 'OpenAI'
          name: aiEmbeddingModelName
          version: aiEmbeddingModelVersion
        }
        sku: {
          name: aiEmbeddingDeploymentType
          capacity: aiEmbeddingModelCapacity
        }
      }
    ]
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    managedIdentities: {
      systemAssigned: true
      userAssignedResourceIds: [appIdentity.outputs.resourceId]
    }
    roleAssignments: [
      // Service Principal permissions
      {
        roleDefinitionIdOrName: 'Cognitive Services OpenAI Contributor'
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: '64702f94-c441-49e6-a78b-ef80e0188fee' // Azure AI Developer
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: '53ca6127-db72-4b80-b1b0-d745d6d5456d' // Foundry User
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      // Deployer permissions for local debugging
      {
        roleDefinitionIdOrName: 'Cognitive Services OpenAI Contributor'
        principalId: deployingUserPrincipalId
        principalType: deployingUserType
      }
      {
        roleDefinitionIdOrName: 'Cognitive Services User'
        principalId: deployingUserPrincipalId
        principalType: deployingUserType
      }
    ]
    // WAF aligned configuration for Monitoring
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    // Private endpoints are deployed separately via the aiFoundryPrivateEndpoint module below
    privateEndpoints: []
    enableTelemetry: enableTelemetry
  }
}

// ========== AI Foundry Private Endpoint ========== //
module aiFoundryPrivateEndpoint 'br/public:avm/res/network/private-endpoint:0.8.1' = if (enablePrivateNetworking && !useExistingAiFoundryAiProject) {
  name: take('pep-${aiFoundryAiServicesResourceName}-deployment', 64)
  dependsOn: [
    aiFoundryAiServices
    virtualNetwork
    avmPrivateDnsZones
  ]
  params: {
    name: 'pep-${aiFoundryAiServicesResourceName}'
    customNetworkInterfaceName: 'nic-${aiFoundryAiServicesResourceName}'
    location: solutionLocation
    tags: allTags
    enableTelemetry: enableTelemetry
    privateLinkServiceConnections: [
      {
        name: 'pep-${aiFoundryAiServicesResourceName}-connection'
        properties: {
          privateLinkServiceId: aiFoundryAiServices!.outputs.resourceId
          groupIds: ['account']
        }
      }
    ]
    privateDnsZoneGroup: {
      privateDnsZoneGroupConfigs: [
        {
          name: 'ai-services-dns-zone-cognitiveservices'
          privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.cognitiveServices]!.outputs.resourceId
        }
        {
          name: 'ai-services-dns-zone-openai'
          privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.openAI]!.outputs.resourceId
        }
        {
          name: 'ai-services-dns-zone-aiservices'
          privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.aiServices]!.outputs.resourceId
        }
      ]
    }
    subnetResourceId: virtualNetwork!.outputs.backendSubnetResourceId
  }
}

// ========== AI Foundry Project ========== //
module aiFoundryProject 'modules/ai-project.bicep' = if (!useExistingAiFoundryAiProject) {
  name: take('module.ai-project.${aiFoundryAiProjectResourceName}', 64)
  dependsOn: enablePrivateNetworking ? [aiFoundryPrivateEndpoint] : []
  params: {
    name: aiFoundryAiProjectResourceName
    location: azureAiServiceLocation
    tags: tags
    desc: aiFoundryAiProjectDescription
    //Implicit dependencies below
    aiServicesName: aiFoundryAiServices!.outputs.name
  }
}

var aiServicesName = useExistingAiFoundryAiProject ? existingAiFoundryAiServices.name : aiFoundryAiServicesResourceName
module appConfiguration 'br/public:avm/res/app-configuration/configuration-store:0.9.1' = {
  name: take('avm.res.app-config.store.${solutionSuffix}', 64)
  params: {
    location: solutionLocation
    name: 'appcs-${solutionSuffix}'
    disableLocalAuth: false // needed to allow setting app config key values from this module
    tags: allTags
    // Always set key values during deployment since Container Apps will be in private network
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
        name: 'AZURE_PACKAGE_LOGGING_LEVEL'
        value: 'INFO'
      }
      {
        name: 'AZURE_LOGGING_PACKAGES'
        value: ''
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
        value: '2025-03-01-preview'
      }
      {
        name: 'AZURE_OPENAI_CHAT_DEPLOYMENT_NAME'
        value: aiModelDeploymentName
      }
      {
        name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME'
        value: aiEmbeddingModelName
      }
      {
        name: 'AZURE_OPENAI_ENDPOINT'
        value: 'https://${aiServicesName}.cognitiveservices.azure.com/'
      }
      {
        name: 'AZURE_OPENAI_ENDPOINT_BASE'
        value: 'https://${aiServicesName}.cognitiveservices.azure.com/'
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
        name: 'COSMOS_DB_CONTROL_CONTAINER_NAME'
        value: processControlCosmosContainerName
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
        name: 'COSMOS_DB_PROCESS_LOG_CONTAINER'
        value: agentTelemetryCosmosContainerName
      }
      {
        name: 'GLOBAL_LLM_SERVICE'
        value: 'AzureOpenAI'
      }
      {
        name: 'STORAGE_QUEUE_ACCOUNT'
        value: storageAccount.outputs.name
      }
    ]
    roleAssignments: [
      {
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: 'App Configuration Data Reader'
      }
    ]
    enableTelemetry: enableTelemetry
    managedIdentities: { systemAssigned: true }
    sku: 'Standard'
    publicNetworkAccess: 'Enabled'
  }
  // Add explicit dependency
  dependsOn: useExistingAiFoundryAiProject ? [] : [aiFoundryAiServices]
}

module avmAppConfigUpdated 'br/public:avm/res/app-configuration/configuration-store:0.6.3' = if (enablePrivateNetworking) {
  name: take('avm.res.app-configuration.configuration-store-update.${solutionSuffix}', 64)
  params: {
    name: 'appcs-${solutionSuffix}'
    location: solutionLocation
    managedIdentities: { systemAssigned: true }
    sku: 'Standard'
    enableTelemetry: enableTelemetry
    tags: allTags
    disableLocalAuth: true
    // Keep public access enabled for Container Apps access (Container Apps not in private network due to capacity constraints)
    publicNetworkAccess: 'Enabled'
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-appconfig-${solutionSuffix}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'appconfig-dns-zone-group'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.appConfig]!.outputs.resourceId
                }
              ]
            }
            subnetResourceId: virtualNetwork!.outputs.backendSubnetResourceId
          }
        ]
      : []
  }
  dependsOn: [
    appConfiguration
  ]
}

var logAnalyticsPrimarySharedKey = useExistingLogAnalytics
  ? existingLogAnalyticsWorkspace!.listKeys().primarySharedKey
  : logAnalyticsWorkspace!.outputs!.primarySharedKey
var logAnalyticsWorkspaceId = useExistingLogAnalytics
  ? existingLogAnalyticsWorkspace!.properties.customerId
  : logAnalyticsWorkspace!.outputs.logAnalyticsWorkspaceId
// ========== Container App Environment ========== //
module containerAppsEnvironment 'br/public:avm/res/app/managed-environment:0.11.2' = {
  name: take('avm.res.app.managed-environment.${solutionSuffix}', 64)
  params: {
    name: 'cae-${solutionSuffix}'
    location: location
    tags: {
      ...resourceGroup().tags
      ...existingTags
      ...allTags
      ...tags
    }
    managedIdentities: { systemAssigned: true }
    appLogsConfiguration: enableMonitoring
      ? {
          destination: 'log-analytics'
          logAnalyticsConfiguration: {
            customerId: logAnalyticsWorkspaceId
            sharedKey: logAnalyticsPrimarySharedKey
          }
        }
      : null
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
    enableTelemetry: enableTelemetry
    publicNetworkAccess: 'Enabled' // Always enabled for Container Apps Environment
    // SFI: enable mTLS / end-to-end encryption between revisions within the
    // Container Apps environment (Container Apps equivalent of App Service's
    // endToEndEncryptionEnabled). Applies to Microsoft.App/managedEnvironments
    // peerTrafficConfiguration.encryption.enabled.
    peerTrafficEncryption: true

    // <========== WAF related parameters

    platformReservedCidr: '172.17.17.0/24'
    platformReservedDnsIP: '172.17.17.17'
    zoneRedundant: (enablePrivateNetworking) ? true : false // Enable zone redundancy if private networking is enabled
    infrastructureSubnetResourceId: (enablePrivateNetworking)
      ? virtualNetwork!.outputs.containersSubnetResourceId // Use the container app subnet
      : null // Use the container app subnet
  }
}

var backendContainerPort = 80
var backendContainerAppName = take('ca-backend-api-${solutionSuffix}', 32)
var processorContainerAppName = take('ca-processor-${solutionSuffix}', 32)
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
    registries: [
      {
        server: containerRegistry.outputs.loginServer
        identity: appIdentity.outputs.resourceId
      }
    ]
    containers: [
      {
        name: 'backend-api'
        image: placeholderContainerImage
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
              name: 'PROCESSOR_CONTROL_URL'
              // Internal ingress FQDN format: https://<app-name>.internal.<environment-default-domain>
              value: 'https://${processorContainerAppName}.internal.${containerAppsEnvironment.outputs.defaultDomain}'
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
      maxReplicas: enableScalability ? 3 : 1
      minReplicas: 1
      rules: enableScalability
        ? [
            {
              name: 'http-scaler'
              http: {
                metadata: {
                  concurrentRequests: 100
                }
              }
            }
          ]
        : []
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

var frontEndContainerAppName = take('ca-frontend-${solutionSuffix}', 32)
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
    registries: [
      {
        server: containerRegistry.outputs.loginServer
        identity: appIdentity.outputs.resourceId
      }
    ]
    containers: [
      {
        name: 'frontend'
        image: placeholderContainerImage
        env: [
          {
            name: 'API_URL'
            value: 'https://${containerAppBackend.outputs.fqdn}'
          }
          {
            name: 'APP_ENV'
            value: 'prod'
          }
          {
            name: 'REACT_APP_MSAL_POST_REDIRECT_URL'
            value: '/'
          }
          {
            name: 'REACT_APP_MSAL_REDIRECT_URL'
            value: '/'
          }
          {
            name: 'ALLOWED_ORIGINS'
            value: 'https://${frontEndContainerAppName}.${containerAppsEnvironment.outputs.defaultDomain}'
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
      maxReplicas: enableScalability ? 3 : 1
      minReplicas: 1
      rules: enableScalability
        ? [
            {
              name: 'http-scaler'
              http: {
                metadata: {
                  concurrentRequests: 100
                }
              }
            }
          ]
        : []
    }
    tags: allTags
    enableTelemetry: enableTelemetry
  }
}

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
    registries: [
      {
        server: containerRegistry.outputs.loginServer
        identity: appIdentity.outputs.resourceId
      }
    ]
    containers: [
      {
        name: 'processor'
        image: placeholderContainerImage
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
            {
              name: 'CONTROL_API_ENABLED'
              value: '1'
            }
            {
              name: 'CONTROL_API_PORT'
              value: '8080'
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
          // TODO - assess increasing resource limits
          cpu: 2
          memory: '4.0Gi'
        }
      }
    ]
    // Internal ingress required for container-to-container communication
    ingressTargetPort: 8080
    ingressExternal: false
    ingressAllowInsecure: true  // Allow HTTP without SSL redirect for internal calls
    scaleSettings: {
      maxReplicas: enableScalability ? 3 : 1
      minReplicas: 1
      //rules: [] - TODO - what scaling rules to use here?
    }
    tags: allTags
    enableTelemetry: enableTelemetry
  }
}

@description('The name of the resource group.')
output resourceGroupName string = resourceGroup().name

@description('The name of the web app container app.')
output CONTAINER_WEB_APP_NAME string = containerAppFrontend.outputs.name

@description('The FQDN of the web app container app.')
output CONTAINER_WEB_APP_FQDN string = containerAppFrontend.outputs.fqdn

@description('The name of the API container app.')
output CONTAINER_API_APP_NAME string = containerAppBackend.outputs.name

@description('The FQDN of the API container app.')
output CONTAINER_API_APP_FQDN string = containerAppBackend.outputs.fqdn

@description('The Azure subscription ID.')
output AZURE_SUBSCRIPTION_ID string = subscription().subscriptionId

@description('The Azure resource group name.')
output AZURE_RESOURCE_GROUP string = resourceGroup().name

@description('The name of the dedicated Azure Container Registry.')
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.outputs.name

@description('The login server (endpoint) of the dedicated Azure Container Registry.')
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer

@description('The name of the processor container app.')
output CONTAINER_PROCESSOR_APP_NAME string = containerAppProcessor.outputs.name

@description('The image tag used for deployment-specific container images.')
output AZURE_ENV_IMAGE_TAG string = imageTag

// Log deployer information for debugging
output deployerObjectId string = deployingUserPrincipalId
output deployerType string = deployingUserType
