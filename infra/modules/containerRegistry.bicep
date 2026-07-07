metadata name = 'Dedicated Azure Container Registry'
metadata description = '''Provisions a dedicated Azure Container Registry (ACR) for a single deployment and configures identity-based authentication.
Admin user and anonymous pull are disabled. The provided application managed identity principals are granted the AcrPull role, and the deployer is granted a registry-scoped AcrPush role so it can push/pull images (remote builds via `az acr build` additionally rely on the deployer's higher-scope role for scheduleRun/action).'''

@description('Required. Name of the Azure Container Registry. Must be globally unique and 5-50 alphanumeric characters.')
@maxLength(50)
param name string

@description('Optional. Azure region for the registry. Defaults to the resource group location.')
param location string = resourceGroup().location

@description('Optional. Tags to apply to the registry.')
param tags object = {}

@description('Optional. SKU for the registry. Premium is required for private networking. Defaults to Standard.')
@allowed([
  'Basic'
  'Standard'
  'Premium'
])
param sku string = 'Standard'

@description('Optional. Public network access for the registry. Defaults to Enabled. Note: `az acr build` (ACR Tasks quick builds) and Container Apps image pulls require reachability; disabling public access requires VNet agent pools and private endpoints, so it is left Enabled by default for both WAF and non-WAF deployments.')
@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string = 'Enabled'

@description('Optional. Whether to allow trusted Azure services (e.g. ACR Tasks used by `az acr build`) to bypass network rules. Defaults to AzureServices.')
@allowed([
  'AzureServices'
  'None'
])
param networkRuleBypassOptions string = 'AzureServices'

@description('Optional. Principal IDs (managed identities) to grant the AcrPull role so they can pull images using identity-based authentication.')
param acrPullPrincipalIds array = []

@description('Optional. Principal ID (e.g. the deployer) to grant a registry-scoped AcrPush role so it can push/pull images. Leave empty to skip.')
param buildPrincipalId string = ''

@description('Optional. Principal type for the build principal.')
@allowed([
  'Device'
  'ForeignGroup'
  'Group'
  'ServicePrincipal'
  'User'
])
param buildPrincipalType string = 'User'

@description('Optional. Resource ID of the subnet to host the registry private endpoint. When set (WAF mode), a private endpoint is created so runtime image pulls flow over the private network.')
param privateEndpointSubnetResourceId string = ''

@description('Optional. Resource ID of the privatelink.azurecr.io private DNS zone to link the private endpoint to.')
param privateDnsZoneResourceId string = ''

// AcrPull role definition ID (allows pulling images).
var acrPullRoleDefinitionId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
// AcrPush role definition ID (least-privilege push/pull for the deployer).
// Note: az acr build (ACR Tasks remote build) additionally needs
// scheduleRun/action, which the deployer holds via its higher-scope role
// (e.g. Owner/Contributor on the subscription or resource group used by azd).
var acrPushRoleDefinitionId = '8311e382-0749-4cb8-b61a-304f252e45ec'

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: sku
  }
  properties: {
    // Identity-based authentication only - no admin credentials.
    adminUserEnabled: false
    // Explicitly disable anonymous pull; access requires an authenticated identity.
    anonymousPullEnabled: false
    publicNetworkAccess: publicNetworkAccess
    networkRuleBypassOptions: networkRuleBypassOptions
    // WAF-aligned networking: when public access is Disabled, default-deny all
    // network traffic (runtime pulls flow over the private endpoint) and disable
    // image export. The DisableExport_PublicNetworkAccessMustBeDisabled constraint
    // requires public access to be Disabled while exports are disabled, so the
    // post-deploy build script toggles both together when it opens the registry.
    networkRuleSet: publicNetworkAccess == 'Disabled' ? { defaultAction: 'Deny' } : null
    policies: publicNetworkAccess == 'Disabled' ? { exportPolicy: { status: 'disabled' } } : null
  }
}

// WAF: private endpoint for runtime image pulls when public access is disabled.
resource registryPrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-11-01' = if (!empty(privateEndpointSubnetResourceId)) {
  name: 'pep-${name}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnetResourceId
    }
    privateLinkServiceConnections: [
      {
        name: 'pls-${name}'
        properties: {
          privateLinkServiceId: registry.id
          groupIds: [
            'registry'
          ]
        }
      }
    ]
  }
}

resource registryPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = if (!empty(privateEndpointSubnetResourceId) && !empty(privateDnsZoneResourceId)) {
  parent: registryPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-azurecr-io'
        properties: {
          privateDnsZoneId: privateDnsZoneResourceId
        }
      }
    ]
  }
}

resource acrPullRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in acrPullPrincipalIds: {
    name: guid(registry.id, principalId, acrPullRoleDefinitionId)
    scope: registry
    properties: {
      roleDefinitionId: subscriptionResourceId(
        'Microsoft.Authorization/roleDefinitions',
        acrPullRoleDefinitionId
      )
      principalId: principalId
      principalType: 'ServicePrincipal'
    }
  }
]

resource acrBuildRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(buildPrincipalId)) {
  name: guid(registry.id, buildPrincipalId, acrPushRoleDefinitionId)
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      acrPushRoleDefinitionId
    )
    principalId: buildPrincipalId
    principalType: buildPrincipalType
  }
}

@description('The resource ID of the container registry.')
output resourceId string = registry.id

@description('The name of the container registry.')
output name string = registry.name

@description('The login server (endpoint) of the container registry, e.g. myregistry.azurecr.io.')
output loginServer string = registry.properties.loginServer
