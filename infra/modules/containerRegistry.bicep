metadata name = 'Dedicated Azure Container Registry'
metadata description = '''Provisions a dedicated Azure Container Registry (ACR) for a single deployment and configures identity-based authentication.
Admin user and anonymous pull are disabled. The provided application managed identity principals are granted the AcrPull role, and the deployer is granted a registry-scoped Contributor role so it can run remote builds (`az acr build`) and push images.'''

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

@description('Optional. Principal ID (e.g. the deployer) to grant a registry-scoped Contributor role so it can run remote builds (az acr build) and push images. Leave empty to skip.')
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

// AcrPull role definition ID (allows pulling images).
var acrPullRoleDefinitionId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
// Contributor role definition ID (allows remote build / scheduleRun + push).
var contributorRoleDefinitionId = 'b24988ac-6180-42a0-ab88-20f7382dd24c'

resource registry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
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
  name: guid(registry.id, buildPrincipalId, contributorRoleDefinitionId)
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      contributorRoleDefinitionId
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
