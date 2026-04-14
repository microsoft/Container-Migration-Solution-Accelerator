# [Optional]: Customizing resource names

By default this template will use the environment name as the prefix to prevent naming collisions within Azure. The parameters below show the default values. You only need to run the statements below if you need to change the values.

> To override any of the parameters, run `azd env set <PARAMETER_NAME> <VALUE>` before running `azd up`. On the first azd command, it will prompt you for the environment name. Be sure to choose 3-20 characters alphanumeric unique name.

## Parameters

| Name                            | Type    | Example Value           | Purpose                                                                               |
| ------------------------------- | ------- | ----------------------- | ------------------------------------------------------------------------------------- |
| `AZURE_ENV_NAME`                | string  | `conmig`                | Sets the environment name prefix for all Azure resources.                             |
| `AZURE_LOCATION`                | string  | `westus`                | Sets the location/region for all Azure resources.                                     |
| `AZURE_ENV_CONTAINER_REGISTRY_ENDPOINT` | string  | `myregistry.azurecr.io` | Specifies the container registry endpoint from which to pull app container images.             |
| `AZURE_ENV_AI_SERVICE_LOCATION`     | string  | `eastus2`               | Specifies the Azure region for AI services (OpenAI/AI Foundry).                       |
| `AZURE_ENV_MODEL_DEPLOYMENT_TYPE`      | string  | `GlobalStandard`        | Defines the model deployment type (allowed values: `Standard`, `GlobalStandard`).     |
| `AZURE_ENV_GPT_MODEL_NAME`           | string  | `o3`                    | Specifies the AI model name.                                                         |
| `AZURE_ENV_GPT_MODEL_VERSION`        | string  | `2025-04-16`            | Specifies the AI model version.                                                      |
| `AZURE_ENV_GPT_MODEL_CAPACITY`       | integer | `200`                   | Sets the model capacity (choose based on your subscription's available capacity). |
| `AZURE_ENV_EXISTING_LOG_ANALYTICS_WORKSPACE_RID` | string | ``             | Optional. Resource ID of an existing Log Analytics workspace to use.                  |
| `AZURE_EXISTING_AIPROJECT_RESOURCE_ID` | string | ``            | Optional. Resource ID of an existing AI Foundry project to use.                       |
| `AZURE_ENV_VM_ADMIN_USERNAME`   | string  | ``                      | The administrator username for the virtual machine.                                   |
| `AZURE_ENV_VM_ADMIN_PASSWORD`   | string  | ``                      | The administrator password for the virtual machine.                                   |
| `AZURE_ENV_IMAGE_TAG`            | string  | `latest`                | Specifies the container image tag to use for deployment.                              |
| `AZURE_ENV_VM_SIZE`             | string  | `Standard_D2s_v5`      | Specifies the VM size for the jumpbox virtual machine (production deployment only).   |

## How to Set a Parameter

To customize any of the above values, run the following command **before** `azd up`:

```bash
azd env set <PARAMETER_NAME> <VALUE>
```

**Example:**

```bash
azd env set AZURE_LOCATION westus2
```
