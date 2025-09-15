@maxLength(44)
@description('Required. Name of the Cosmos DB Account.')
param name string

@description('Required. Specifies the location for all the Azure resources.')
param location string

@description('Optional. Specifies the resource tags for all the resources.')
param tags resourceInput<'Microsoft.Resources/resourceGroups@2025-04-01'>.tags = {}

@description('Required. Name of application database in the Cosmos DB account')
param databaseName string

@description('Optional. List of containers to create in the database.')
param containers string[]?

@description('Optional. Resource Id of an existing subnet to use for private connectivity. This is required along with \'sqlPrivateDnsZoneResourceId\' to establish a private endpoint.')
param privateEndpointSubnetResourceId string?

@description('Optional. The resource ID of the private DNS zone for the Cosmos DB SQL service to establish a private endpoint.')
param sqlPrivateDnsZoneResourceId string?

@description('Optional. Managed Identity principal ID to assign SQL data plane roles for the Cosmos DB Account.')
param dataAccessIdentityPrincipalId string?

@description('Optional. The resource ID of an existing Log Analytics workspace to associate with AI Foundry for monitoring.')
param logAnalyticsWorkspaceResourceId string?

@description('Required. Indicates whether the single-region account is zone redundant. This property is ignored for multi-region accounts.')
param zoneRedundant bool

@description('Optional. The secondary location for the Cosmos DB Account for failover and multiple writes.')
param secondaryLocation string?

import { roleAssignmentType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@description('Optional. Array of role assignments to create.')
param roleAssignments roleAssignmentType[]?

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

resource sqlContributorRoleDefinition 'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions@2024-11-15' existing = {
  name: '${name}/00000000-0000-0000-0000-000000000002'
}

var privateNetworkingEnabled = !empty(sqlPrivateDnsZoneResourceId) && !empty(privateEndpointSubnetResourceId)

module cosmosAccount 'br/public:avm/res/document-db/database-account:0.15.1' = {
  name: take('avm.res.document-db.account.${name}', 64)
  params: {
    name: name
    enableAnalyticalStorage: true
    location: location
    minimumTlsVersion: 'Tls12'
    defaultConsistencyLevel: 'Session'
    networkRestrictions: {
      networkAclBypass: 'AzureServices'
      publicNetworkAccess: privateNetworkingEnabled ? 'Disabled' : 'Enabled'
      ipRules: []
      virtualNetworkRules: []
    }
    zoneRedundant: zoneRedundant
    automaticFailover: !empty(secondaryLocation)
    failoverLocations: !empty(secondaryLocation)
      ? [
          {
            failoverPriority: 0
            isZoneRedundant: zoneRedundant
            locationName: location
          }
          {
            failoverPriority: 1
            isZoneRedundant: zoneRedundant
            locationName: secondaryLocation!
          }
        ]
      : []
    enableMultipleWriteLocations: !empty(secondaryLocation)
    backupPolicyType: !empty(secondaryLocation) ? 'Periodic' : 'Continuous'
    backupStorageRedundancy: zoneRedundant ? 'Zone' : 'Local'
    disableKeyBasedMetadataWriteAccess: false
    disableLocalAuthentication: privateNetworkingEnabled
    diagnosticSettings: !empty(logAnalyticsWorkspaceResourceId)? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }]: []
    privateEndpoints: privateNetworkingEnabled
      ? [
          {
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  privateDnsZoneResourceId: sqlPrivateDnsZoneResourceId!
                }
              ]
            }
            service: 'Sql'
            subnetResourceId: privateEndpointSubnetResourceId!
          }
        ]
      : []
    sqlDatabases: [
      {
        containers: [
          for container in (containers ?? []) : {
            indexingPolicy: {
              automatic: true
            }
            name: container
            paths: [
              '/_partitionKey'
            ]
          }
        ]
        name: databaseName
      }
    ]
    dataPlaneRoleAssignments: !empty(dataAccessIdentityPrincipalId) ? [
      {
        principalId: dataAccessIdentityPrincipalId!
        roleDefinitionId: sqlContributorRoleDefinition.id
      }
    ] : []
    roleAssignments: roleAssignments
    tags: tags
    enableTelemetry: enableTelemetry
  }
}

@description('Name of the Cosmos DB Account resource.')
output name string = cosmosAccount.outputs.name

@description('Resource ID of the Cosmos DB Account.')
output resourceId string = cosmosAccount.outputs.resourceId

@description('Name of the resource group containing the Cosmos DB Account.')
output resourceGroupName string = resourceGroup().name

@description('Endpoint of the Cosmos DB Account.')
output endpoint string = cosmosAccount.outputs.endpoint

