@maxLength(24)
@description('Required. The name of the storage account.')
param name string

@description('Required. The location for the storage account.')
param location string

@allowed([
  'Standard_LRS'
  'Standard_GRS'
  'Standard_RAGRS'
  'Standard_ZRS'
  'Premium_LRS'
  'Premium_ZRS'
  'Standard_GZRS'
  'Standard_RAGZRS'
])
@description('Optional. Storage Account Sku Name. Defaults to Standard_LRS.')
param skuName string = 'Standard_LRS'

@description('Optional. Resource Id of an existing subnet to use for private connectivity. This is required along with \'blobPrivateDnsZoneResourceId\' to establish private endpoints.')
param privateEndpointSubnetResourceId string?

@description('Optional. The resource ID of the private DNS zone for the storage account blob service to establish private endpoints.')
param blobPrivateDnsZoneResourceId string?

@description('Optional. The resource ID of the private DNS zone for the storage account queue service to establish private endpoints.')
param queuePrivateDnsZoneResourceId string?

@description('Optional. List of blob containers to create in the storage account.')
param containers string[]?

@description('Optional. List of queues to create in the storage account.')
param queues string[]?

@description('Optional. The resource ID of the log analytics workspace to send diagnostic logs to.')
param logAnalyticsWorkspaceResourceId string?

import { roleAssignmentType } from 'br/public:avm/utl/types/avm-common-types:0.6.0'
@description('Optional. Specifies the role assignments for the storage account.')
param roleAssignments roleAssignmentType[]?

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Optional. Specifies the resource tags for all the resources.')
param tags resourceInput<'Microsoft.Resources/resourceGroups@2025-04-01'>.tags = {}

var privateNetworkingEnabled = (!empty(blobPrivateDnsZoneResourceId) || !empty(queuePrivateDnsZoneResourceId)) && !empty(privateEndpointSubnetResourceId)

module storageAccount 'br/public:avm/res/storage/storage-account:0.26.2' = {
  name: take('avm.res.storage.storage-account.${name}', 64)
  params: {
    name: name
    location: location
    skuName: skuName
    tags: tags
    enableTelemetry: enableTelemetry
    publicNetworkAccess: privateNetworkingEnabled ? 'Disabled' : 'Enabled'
    accessTier: 'Hot'
    allowBlobPublicAccess: !privateNetworkingEnabled
    allowSharedKeyAccess: false
    allowCrossTenantReplication: false
    blobServices: {
      deleteRetentionPolicyEnabled: true
      deleteRetentionPolicyDays: 7
      containerDeleteRetentionPolicyEnabled: true
      containerDeleteRetentionPolicyDays: 7
      containers: [
        for container in (containers ?? []): {
          name: container
        }
      ]
    }
    queueServices: {
      deleteRetentionPolicyEnabled: true
      deleteRetentionPolicyDays: 7
      queues: [
        for queue in (queues ?? []): {
          name: queue
        }
      ]
    }
    minimumTlsVersion: 'TLS1_2'
    networkAcls: {
      defaultAction: privateNetworkingEnabled ? 'Deny' : 'Allow'
      bypass: 'AzureServices'
    }
    supportsHttpsTrafficOnly: true
    diagnosticSettings: !empty(logAnalyticsWorkspaceResourceId)
      ? [
          {
            workspaceResourceId: logAnalyticsWorkspaceResourceId
          }
        ]
      : []
    privateEndpoints: privateNetworkingEnabled
      ? concat(!empty(blobPrivateDnsZoneResourceId) ? [
          {
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  privateDnsZoneResourceId: blobPrivateDnsZoneResourceId!
                }
              ]
            }
            service: 'blob'
            subnetResourceId: privateEndpointSubnetResourceId!
          }
        ] : [],
        !empty(queuePrivateDnsZoneResourceId) ? [
          {
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  privateDnsZoneResourceId: queuePrivateDnsZoneResourceId!
                }
              ]
            }
            service: 'queue'
            subnetResourceId: privateEndpointSubnetResourceId!
          }
        ] : [])
      : []
    roleAssignments: roleAssignments
  }
}

@description('Name of the Storage Account.')
output name string = storageAccount!.outputs.name

@description('Resource ID of the Storage Account.')
output resourceId string = storageAccount!.outputs.resourceId

@description('Resource Group Name of the Storage Account.')
output resourceGroupName string = resourceGroup().name

@description('Blob service endpoint of the Storage Account.')
output blobEndpoint string = 'https://${name}.blob.${environment().suffixes.storage}'

@description('Queue service endpoint of the Storage Account.')
output queueEndpoint string = 'https://${name}.queue.${environment().suffixes.storage}'
