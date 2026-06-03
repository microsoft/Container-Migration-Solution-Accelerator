# AVM (Azure Verified Modules) Infrastructure

This folder is a **scaffold** for an Azure Verified Modules (AVM) based
implementation of the Container Migration Solution Accelerator's infrastructure.

It mirrors the structure used in
[`microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator` (`psl/infra-restructure-new`)](https://github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator/tree/psl/infra-restructure-new/infra)
and the private repo
[`mcaps-microsoft/accelerator-toolkit-core` (`psl/infra`)](https://github.com/mcaps-microsoft/accelerator-toolkit-core/tree/psl/infra),
where AVM and custom Bicep implementations live side-by-side under `infra/`.

## Status

Empty placeholder. The active deployment still uses the templates under
[`infra/`](../) (top level) and the duplicate copy under
[`infra/bicep/`](../bicep). When the AVM rewrite is implemented:

- `infra/avm/main.bicep` &mdash; AVM-based root template.
- `infra/avm/main.json` &mdash; compiled ARM (generated via `az bicep build`).
- `infra/avm/modules/` &mdash; thin wrappers around `br/public:avm/res/...`
  modules for Container Apps, Cosmos DB, AI Services / AI Foundry, Storage,
  Log Analytics, App Insights, VNet, Bastion, etc.

## Resources to be covered (per User Story 45200)

Core:

- Azure AI Services + AI Foundry Project
- OpenAI / Embedding model deployments
- Cosmos DB
- Storage Account
- Container Apps Environment + Backend / Frontend / Processor Container Apps
- App Configuration
- User Assigned Managed Identity
- Container Registry

Conditional (Monitoring):

- Log Analytics Workspace
- Application Insights

Conditional (Networking):

- Virtual Network + subnets
- Bastion Host
- Private DNS Zones
- Private Endpoints
- Jumpbox VM

> Note: the existing top-level `main.bicep` already consumes a number of AVM
> public registry modules (e.g. `avm/res/managed-identity/...`,
> `avm/res/operational-insights/workspace`, `avm/res/insights/component`).
> The AVM rewrite under this folder will consolidate **all** resources to AVM
> public modules where available.
