@description('Required. Named used for all resource naming.')
param resourcesName string

@description('Required. Resource ID of the Log Analytics Workspace for monitoring and diagnostics.')
param logAnalyticsWorkSpaceResourceId string

@minLength(3)
@description('Required. Azure region for all services.')
param location string

@description('Optional. Tags to be applied to the resources.')
param tags object = {}

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Required. Admin username for the VM.')
@secure()
param vmAdminUsername string

@description('Required. Admin password for the VM.')
@secure()
param vmAdminPassword string

@description('Required. VM size for the Jumpbox VM.')
param vmSize string

// VM Size Notes:
// 1 B-series VMs (like Standard_B2ms) do not support accelerated networking.
// 2 Pick a VM size that does support accelerated networking (the usual jump-box candidates):
//     Standard_DS2_v2 (2 vCPU, 7 GiB RAM, Premium SSD) // The most broadly available (it’s a legacy SKU supported in virtually every region).
//     Standard_D2s_v3 (2 vCPU, 8 GiB RAM, Premium SSD) //  next most common
//     Standard_D2s_v4 (2 vCPU, 8 GiB RAM, Premium SSD)  // Newest, so fewer regions availabl

// Subnet Classless Inter-Doman Routing (CIDR)  Sizing Reference Table (Best Practices)
// | CIDR      | # of Addresses | # of /24s | Notes                                 |
// |-----------|---------------|-----------|----------------------------------------|
// | /24       | 256           | 1         | Smallest recommended for Azure subnets |
// | /23       | 512           | 2         | Good for 1-2 workloads per subnet      |
// | /22       | 1024          | 4         | Good for 2-4 workloads per subnet      |
// | /21       | 2048          | 8         |                                        |
// | /20       | 4096          | 16        | Used for default VNet in this solution |
// | /19       | 8192          | 32        |                                        |
// | /18       | 16384         | 64        |                                        |
// | /17       | 32768         | 128       |                                        |
// | /16       | 65536         | 256       |                                        |
// | /15       | 131072        | 512       |                                        |
// | /14       | 262144        | 1024      |                                        |
// | /13       | 524288        | 2048      |                                        |
// | /12       | 1048576       | 4096      |                                        |
// | /11       | 2097152       | 8192      |                                        |
// | /10       | 4194304       | 16384     |                                        |
// | /9        | 8388608       | 32768     |                                        |
// | /8        | 16777216      | 65536     |                                        |
//
// Best Practice Notes:
// - Use /24 as the minimum subnet size for Azure (smaller subnets are not supported for most services).
// - Plan for future growth: allocate larger address spaces (e.g., /20 or /21 for VNets) to allow for new subnets.
// - Avoid overlapping address spaces with on-premises or other VNets.
// - Use contiguous, non-overlapping ranges for subnets.
// - Document subnet usage and purpose in code comments.
// - For AVM modules, ensure only one delegation per subnet and leave delegations empty if not required.

module network 'network/main.bicep' = {
  name: take('network-${resourcesName}-create', 64)
  params: {
    resourcesName: resourcesName
    location: location
    logAnalyticsWorkSpaceResourceId: logAnalyticsWorkSpaceResourceId
    tags: tags
    // Expanded VNet address space to include a 192.168.0.0/20 block so that subnets needing 172.x or 192.x ranges (required by some AI/AML network injections) are valid.
    // NOTE: Cognitive Services / AI Foundry (AML RP virtual workspace) rejected the previous 10.x based private endpoint subnet with error:
    //   "Provided subnet must be of the proper address space. Please provide a subnet which has address space in the range of 172 or 192."
    // Adding a secondary address space avoids re-addressing existing 10.x subnets.
    // Updated to /20 to accommodate both 'peps' (/23) and 'agents' (/23) subnets within 192.168.0.0/20 range
    addressPrefixes: ['10.0.0.0/20'] // existing workloads + dedicated AI/private endpoints + agent services
    subnets: [
      // Only one delegation per subnet is supported by the AVM module as of June 2025.
      // For subnets that do not require delegation, leave the value empty.
      {
        name: 'web'
        addressPrefixes: ['10.0.0.0/23'] // /23 (10.0.0.0 - 10.0.1.255), 512 addresses
        networkSecurityGroup: {
          name: 'nsg-web'
          securityRules: [
            {
              name: 'AllowHttpsInbound'
              properties: {
                access: 'Allow'
                direction: 'Inbound'
                priority: 100
                protocol: 'Tcp'
                sourcePortRange: '*'
                destinationPortRange: '443'
                sourceAddressPrefixes: ['0.0.0.0/0']
                destinationAddressPrefixes: ['10.0.0.0/23']
              }
            }
            {
              name: 'AllowIntraSubnetTraffic'
              properties: {
                access: 'Allow'
                direction: 'Inbound'
                priority: 200
                protocol: '*'
                sourcePortRange: '*'
                destinationPortRange: '*'
                sourceAddressPrefixes: ['10.0.0.0/23'] // From same subnet
                destinationAddressPrefixes: ['10.0.0.0/23'] // To same subnet
              }
            }
            {
              name: 'AllowAzureLoadBalancer'
              properties: {
                access: 'Allow'
                direction: 'Inbound'
                priority: 300
                protocol: '*'
                sourcePortRange: '*'
                destinationPortRange: '*'
                sourceAddressPrefix: 'AzureLoadBalancer'
                destinationAddressPrefix: '10.0.0.0/23'
              }
            }
          ]
        }
        delegation: 'Microsoft.Web/serverFarms'
      }
      {
        name: 'peps'
        // Moved to 192.168.0.0/22 to satisfy AML / Cognitive Services requirement for 172.x or 192.x address space for the virtual workspace / network injection.
        // /22 (192.168.0.0 - 192.168.3.255) 1024 addresses - split into two /23 subnets
        addressPrefixes: ['10.0.5.0/24']
        privateEndpointNetworkPolicies: 'Disabled'
        privateLinkServiceNetworkPolicies: 'Disabled'
        networkSecurityGroup: {
          name: 'nsg-peps'
          securityRules: []
        }
      }
      {
        name: 'containers'
        addressPrefixes: ['10.0.2.0/24'] // /24 (10.0.2.0 - 10.0.2.255), 256 addresses
        delegation: 'Microsoft.App/environments'
        networkSecurityGroup: {
          name: 'nsg-containers'
          securityRules: [
            //Inbound Rules
            {
              name: 'AllowHttpsInbound'
              properties: {
                access: 'Allow'
                direction: 'Inbound'
                priority: 100
                protocol: 'Tcp'
                sourceAddressPrefix: 'Internet'
                sourcePortRange: '*'
                destinationPortRanges: ['443', '80']
                destinationAddressPrefixes: ['10.0.2.0/24']
              }
            }
            {
              name: 'AllowAzureLoadBalancerInbound'
              properties: {
                access: 'Allow'
                direction: 'Inbound'
                priority: 102
                protocol: '*'
                sourceAddressPrefix: 'AzureLoadBalancer'
                sourcePortRange: '*'
                destinationPortRanges: ['30000-32767']
                destinationAddressPrefixes: ['10.0.2.0/24']
              }
            }
            {
              name: 'AllowSideCarsInbound'
              properties: {
                access: 'Allow'
                direction: 'Inbound'
                priority: 103
                protocol: '*'
                sourcePortRange: '*'
                sourceAddressPrefixes: ['10.0.2.0/24']
                destinationPortRange: '*'
                destinationAddressPrefix: '*'
              }
            }
            //Outbound Rules
            {
              name: 'AllowOutboundToAzureServices'
              properties: {
                access: 'Allow'
                direction: 'Outbound'
                priority: 200
                protocol: '*'
                sourceAddressPrefixes: ['10.0.2.0/24']
                sourcePortRange: '*'
                destinationPortRange: '*'
                destinationAddressPrefix: '*'
              }
            }
            {
              name: 'deny-hop-outbound'
              properties: {
                access: 'Deny'
                direction: 'Outbound'
                priority: 100
                protocol: '*'
                sourcePortRange: '*'
                destinationPortRanges: ['3389', '22']
                sourceAddressPrefix: 'VirtualNetwork'
                destinationAddressPrefix: '*'
              }
            }
          ]
        }
      }
    ]
    bastionConfiguration: {
      name: 'bas-${resourcesName}'
      subnet: {
        name: 'AzureBastionSubnet'
        addressPrefixes: ['10.0.10.0/26']
        networkSecurityGroup: {
          name: 'nsg-AzureBastionSubnet'
          securityRules: [
            {
              name: 'AllowGatewayManager'
              properties: {
                access: 'Allow'
                direction: 'Inbound'
                priority: 2702
                protocol: '*'
                sourcePortRange: '*'
                destinationPortRange: '443'
                sourceAddressPrefix: 'GatewayManager'
                destinationAddressPrefix: '*'
              }
            }
            {
              name: 'AllowHttpsInBound'
              properties: {
                access: 'Allow'
                direction: 'Inbound'
                priority: 2703
                protocol: '*'
                sourcePortRange: '*'
                destinationPortRange: '443'
                sourceAddressPrefix: 'Internet'
                destinationAddressPrefix: '*'
              }
            }
            {
              name: 'AllowSshRdpOutbound'
              properties: {
                access: 'Allow'
                direction: 'Outbound'
                priority: 100
                protocol: '*'
                sourcePortRange: '*'
                destinationPortRanges: ['22', '3389']
                sourceAddressPrefix: '*'
                destinationAddressPrefix: 'VirtualNetwork'
              }
            }
            {
              name: 'AllowAzureCloudOutbound'
              properties: {
                access: 'Allow'
                direction: 'Outbound'
                priority: 110
                protocol: 'Tcp'
                sourcePortRange: '*'
                destinationPortRange: '443'
                sourceAddressPrefix: '*'
                destinationAddressPrefix: 'AzureCloud'
              }
            }
          ]
        }
      }
    }
    jumpboxConfiguration: {
      name: 'vm-jumpbox-${resourcesName}'
      size: vmSize
      username: vmAdminUsername
      password: vmAdminPassword
      subnet: {
        name: 'jumpbox'
        addressPrefixes: ['10.0.12.0/23'] // /23 (10.0.12.0 - 10.0.13.255), 512 addresses
        networkSecurityGroup: {
          name: 'nsg-jumbox'
          securityRules: [
            {
              name: 'AllowRdpFromBastion'
              properties: {
                access: 'Allow'
                direction: 'Inbound'
                priority: 100
                protocol: 'Tcp'
                sourcePortRange: '*'
                destinationPortRange: '3389'
                sourceAddressPrefixes: [
                  '10.0.10.0/26' // Azure Bastion subnet
                ]
                destinationAddressPrefixes: ['10.0.12.0/23']
              }
            }
          ]
        }
      }
    }
    enableTelemetry: enableTelemetry
  }
}

@description('Name of the Virtual Network resource.')
output vnetName string = network.outputs.vnetName

@description('Resource ID of the Virtual Network.')
output vnetResourceId string = network.outputs.vnetResourceId

@description('Resource ID of the "web" subnet.')
output subnetWebResourceId string = first(filter(network.outputs.subnets, s => s.name == 'web')).?resourceId ?? ''

@description('Resource ID of the "peps" subnet for Private Endpoints.')
output subnetPrivateEndpointsResourceId string = first(filter(network.outputs.subnets, s => s.name == 'peps')).?resourceId ?? ''

@description('Resource ID of the "containers" subnet for AI Foundry container services.')
output subnetContainerServiceResourceId string = first(filter(network.outputs.subnets, s => s.name == 'containers')).?resourceId ?? ''

@description('Resource ID of the Bastion Host.')
output bastionResourceId string = network.outputs.bastionHostId

@description('Resource ID of the Jumpbox VM.')
output jumpboxResourceId string = network.outputs.jumpboxResourceId
