# [Optional]: Customizing resource names

By default this template will use the environment name as the prefix to prevent naming collisions within Azure. The parameters below show the default values. You only need to run the statements below if you need to change the values.

> To override any of the parameters, run `azd env set <PARAMETER_NAME> <VALUE>` before running `azd up`. On the first azd command, it will prompt you for the environment name. Be sure to choose 3-20 characters alphanumeric unique name.

## Parameters

| Name                            | Type    | Example Value           | Purpose                                                                               |
| ------------------------------- | ------- | ----------------------- | ------------------------------------------------------------------------------------- |
| `AZURE_ENV_NAME`                | string  | `conmig`                | Sets the environment name prefix for all Azure resources.                             |
| `AZURE_LOCATION`                | string  | `westus`                | Sets the location/region for all Azure resources.                                     |
| `AZURE_CONTAINER_REGISTRY_HOST` | string  | `myregistry.azurecr.io` | Specifies the container registry from which to pull app container images.             |
| `AZURE_AI_SERVICE_LOCATION`     | string  | `eastus2`               | Specifies the Azure region for AI services (OpenAI/AI Foundry).                       |
| `AZURE_AI_DEPLOYMENT_TYPE`      | string  | `GlobalStandard`        | Defines the model deployment type (allowed values: `Standard`, `GlobalStandard`).     |
| `AZURE_AI_MODEL_NAME`           | string  | `o3`                    | Specifies the `o` model name.                                                         |
| `AZURE_AI_MODEL_VERSION`        | string  | `2025-04-16`            | Specifies the `o` model version.                                                      |
| `AZURE_AI_MODEL_CAPACITY`       | integer | `200`                   | Sets the model capacity (choose based on your subscription's available `o` capacity). |
| `AZURE_ENV_LOG_ANALYTICS_WORKSPACE_ID` | string | ``             | Optional. Resource ID of an existing Log Analytics workspace to use.                  |
| `AZURE_EXISTING_AI_PROJECT_RESOURCE_ID` | string | ``            | Optional. Resource ID of an existing AI Foundry project to use.                       |
| `AZURE_ENV_VM_ADMIN_USERNAME`   | string  | ``                      | The administrator username for the virtual machine.                                   |
| `AZURE_ENV_VM_ADMIN_PASSWORD`   | string  | ``                      | The administrator password for the virtual machine.                                   |
| `AZURE_ENV_IMAGETAG`            | string  | `latest`                | Specifies the container image tag to use for deployment.                              |

## How to Set a Parameter

To customize any of the above values, run the following command **before** `azd up`:

```bash
azd env set <PARAMETER_NAME> <VALUE>
```

**Example:**

```bash
azd env set AZURE_LOCATION westus2
```
