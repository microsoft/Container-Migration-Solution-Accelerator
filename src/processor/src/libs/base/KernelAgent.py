from enum import Enum
import logging
from typing import Any

from azure.core.credentials import AccessToken
from azure.identity import (
    get_bearer_token_provider,
)
from pydantic import Field, PrivateAttr, ValidationError
from semantic_kernel.agents import (
    AzureAIAgent,
    AzureAIAgentSettings,
    AzureAssistantAgent,
    ChatCompletionAgent,
)
from semantic_kernel.connectors.ai.azure_ai_inference import (
    AzureAIInferenceChatPromptExecutionSettings,
)
from semantic_kernel.connectors.ai.function_choice_behavior import (
    FunctionChoiceBehavior,
)
from semantic_kernel.connectors.ai.open_ai import (
    AzureChatCompletion,
    AzureChatPromptExecutionSettings,
)
from semantic_kernel.exceptions.service_exceptions import ServiceInitializationError
from semantic_kernel.functions import KernelArguments, KernelFunction, KernelPlugin
from semantic_kernel.kernel import Kernel
from semantic_kernel.prompt_template import PromptTemplateConfig
from semantic_kernel.filters.filter_types import FilterTypes

from libs.base.AppConfiguration import semantic_kernel_settings
from libs.base.SKBase import SKBaseModel
from utils.credential_util import get_async_azure_credential, get_azure_credential
from utils.tool_invocation_filter import ToolInvocationFilter


class service_type(Enum):
    Chat_Completion = "ChatCompletion"
    Text_Completion = "TextCompletion"


class semantic_kernel_agent(SKBaseModel):
    kernel: Kernel = Field(default_factory=Kernel)
    plugins_directory: str | None = None
    _settings: semantic_kernel_settings | None = PrivateAttr(default=None)
    _cached_credential_token: AccessToken | None = PrivateAttr(default=None)

    _use_entra_id: bool = True
    _environment_file_path: str | None = None
    _custom_service_prefixes: dict[str, str] | None = None

    def __init__(
        self,
        env_file_path: str | None = None,
        custom_service_prefixes: dict[str, str] | None = None,
        use_entra_id: bool = True,
        **data,
    ):
        super().__init__(**data)
        self.kernel = Kernel()
        self._use_entra_id = use_entra_id
        self._environment_file_path = env_file_path
        self._custom_service_prefixes = custom_service_prefixes

        # SECURITY: Register auto-function-invocation filter to validate every
        # tool call against the approved allow-list before execution.
        self.kernel.add_filter(
            FilterTypes.AUTO_FUNCTION_INVOCATION,
            ToolInvocationFilter(),
        )

        # self._initialize_settings(
        #     env_file_path=env_file_path,
        #     custom_service_prefixes=custom_service_prefixes,
        #     use_entra_id=use_entra_id,
        # )

    # def _get_azure_credential(self):
    #     """
    #     Get the appropriate Azure credential based on environment.

    #     Following Azure authentication best practices:
    #     - Local Development: Use AzureCliCredential (requires 'az login')
    #     - Azure Container/VM: Use ManagedIdentityCredential (role-based auth)
    #     - Azure App Service/Functions: Use ManagedIdentityCredential
    #     - Fallback: DefaultAzureCredential with explicit instantiation

    #     This pattern ensures:
    #     - Local dev uses 'az login' credentials
    #     - Azure-hosted containers use assigned managed identity roles
    #     - Production environments get proper RBAC-based authentication
    #     """
    #     import os

    #     # Check if running in Azure environment (container, app service, VM, etc.)
    #     azure_env_indicators = [
    #         "WEBSITE_SITE_NAME",  # App Service
    #         "AZURE_CLIENT_ID",  # User-assigned managed identity
    #         "MSI_ENDPOINT",  # System-assigned managed identity
    #         "IDENTITY_ENDPOINT",  # Newer managed identity endpoint
    #         "KUBERNETES_SERVICE_HOST",  # AKS container
    #         "CONTAINER_REGISTRY_LOGIN",  # Azure Container Registry
    #     ]

    #     # Check for checking current environment - Hoster (Azure / Cli on Local)
    #     if any(os.getenv(indicator) for indicator in azure_env_indicators):
    #         # Running in Azure - use Managed Identity for role-based authentication
    #         logging.info(
    #             "[AUTH] Detected Azure environment - using ManagedIdentityCredential for role-based auth"
    #         )

    #         # Check if user-assigned managed identity is specified
    #         client_id = os.getenv("AZURE_CLIENT_ID")
    #         if client_id:
    #             logging.info(
    #                 f"[AUTH] Using user-assigned managed identity: {client_id}"
    #             )
    #             return ManagedIdentityCredential(client_id=client_id)
    #         else:
    #             logging.info("[AUTH] Using system-assigned managed identity")
    #             return ManagedIdentityCredential()

    #     # Local development - try multiple CLI credentials
    #     credential_attempts = []

    #     # Try Azure Developer CLI first (newer, designed for development)
    #     try:
    #         logging.info(
    #             "[AUTH] Local development detected - trying AzureDeveloperCliCredential (requires 'azd auth login')"
    #         )
    #         credential = AzureDeveloperCliCredential()
    #         credential_attempts.append(("AzureDeveloperCliCredential", credential))
    #     except Exception as e:
    #         logging.warning(f"[AUTH] AzureDeveloperCliCredential failed: {e}")

    #     # Try Azure CLI as fallback (traditional)
    #     try:
    #         logging.info("[AUTH] Trying AzureCliCredential (requires 'az login')")
    #         credential = AzureCliCredential()
    #         credential_attempts.append(("AzureCliCredential", credential))
    #     except Exception as e:
    #         logging.warning(f"[AUTH] AzureCliCredential failed: {e}")

    #     # Return the first successful credential
    #     if credential_attempts:
    #         credential_name, credential = credential_attempts[0]
    #         logging.info(f"[AUTH] Using {credential_name} for local development")
    #         return credential

    #     # Final fallback to DefaultAzureCredential
    #     logging.info(
    #         "[AUTH] All CLI credentials failed - falling back to DefaultAzureCredential"
    #     )
    #     return DefaultAzureCredential()

    # def _get_async_azure_credential(self):
    #     """
    #     Get the appropriate async Azure credential based on environment.
    #     Used for Azure services that require async credentials like AzureAIAgent.
    #     """
    #     import os

    #     # Check if running in Azure environment (container, app service, VM, etc.)
    #     azure_env_indicators = [
    #         "WEBSITE_SITE_NAME",  # App Service
    #         "AZURE_CLIENT_ID",  # User-assigned managed identity
    #         "MSI_ENDPOINT",  # System-assigned managed identity
    #         "IDENTITY_ENDPOINT",  # Newer managed identity endpoint
    #         "KUBERNETES_SERVICE_HOST",  # AKS container
    #         "CONTAINER_REGISTRY_LOGIN",  # Azure Container Registry
    #     ]

    #     # Check for checking current environment - Hoster (Azure / Cli on Local)
    #     if any(os.getenv(indicator) for indicator in azure_env_indicators):
    #         # Running in Azure - use Managed Identity for role-based authentication
    #         logging.info(
    #             "[AUTH] Detected Azure environment - using async ManagedIdentityCredential for role-based auth"
    #         )

    #         # Check if user-assigned managed identity is specified
    #         client_id = os.getenv("AZURE_CLIENT_ID")
    #         if client_id:
    #             logging.info(
    #                 f"[AUTH] Using async user-assigned managed identity: {client_id}"
    #             )
    #             return AsyncManagedIdentityCredential(client_id=client_id)
    #         else:
    #             logging.info("[AUTH] Using async system-assigned managed identity")
    #             return AsyncManagedIdentityCredential()

    #     # Local development - try multiple CLI credentials
    #     credential_attempts = []

    #     # Try Azure Developer CLI first (newer, designed for development)
    #     try:
    #         logging.info(
    #             "[AUTH] Local development detected - trying async AzureDeveloperCliCredential (requires 'azd auth login')"
    #         )
    #         credential = AsyncAzureDeveloperCliCredential()
    #         credential_attempts.append(("AsyncAzureDeveloperCliCredential", credential))
    #     except Exception as e:
    #         logging.warning(f"[AUTH] AsyncAzureDeveloperCliCredential failed: {e}")

    #     # Try Azure CLI as fallback (traditional)
    #     try:
    #         logging.info("[AUTH] Trying async AzureCliCredential (requires 'az login')")
    #         credential = AsyncAzureCliCredential()
    #         credential_attempts.append(("AsyncAzureCliCredential", credential))
    #     except Exception as e:
    #         logging.warning(f"[AUTH] AsyncAzureCliCredential failed: {e}")

    #     # Return the first successful credential
    #     if credential_attempts:
    #         credential_name, credential = credential_attempts[0]
    #         logging.info(f"[AUTH] Using {credential_name} for local development")
    #         return credential

    #     # Final fallback to DefaultAzureCredential
    #     logging.info(
    #         "[AUTH] All async CLI credentials failed - falling back to AsyncDefaultAzureCredential"
    #     )
    #     return AsyncDefaultAzureCredential()

    def validate_azure_authentication(self) -> dict[str, Any]:
        """
        Validate Azure authentication setup and provide helpful diagnostics.

        Returns:
            dict with authentication status, credential type, and recommendations
        """
        import os

        auth_info = {
            "status": "unknown",
            "credential_type": "none",
            "environment": "unknown",
            "recommendations": [],
            "azure_env_indicators": {},
        }

        # Check environment indicators
        azure_indicators = {
            "WEBSITE_SITE_NAME": os.getenv("WEBSITE_SITE_NAME"),
            "AZURE_CLIENT_ID": os.getenv("AZURE_CLIENT_ID"),
            "MSI_ENDPOINT": os.getenv("MSI_ENDPOINT"),
            "IDENTITY_ENDPOINT": os.getenv("IDENTITY_ENDPOINT"),
            "KUBERNETES_SERVICE_HOST": os.getenv("KUBERNETES_SERVICE_HOST"),
        }

        auth_info["azure_env_indicators"] = {
            k: v for k, v in azure_indicators.items() if v
        }

        if any(azure_indicators.values()):
            auth_info["environment"] = "azure_hosted"
            auth_info["credential_type"] = "managed_identity"
            if os.getenv("AZURE_CLIENT_ID"):
                auth_info["recommendations"].append(
                    "Using user-assigned managed identity - ensure proper RBAC roles assigned"
                )
            else:
                auth_info["recommendations"].append(
                    "Using system-assigned managed identity - ensure it's enabled and has proper RBAC roles"
                )
        else:
            auth_info["environment"] = "local_development"
            auth_info["credential_type"] = "cli_credentials"
            auth_info["recommendations"].extend(
                [
                    "For local development, authenticate using one of:",
                    "  • Azure Developer CLI: 'azd auth login' (recommended for development)",
                    "  • Azure CLI: 'az login' (traditional method)",
                    "Both methods are supported and will be tried automatically",
                    "Ensure you have access to required Azure resources",
                    "Consider using 'az account show' to verify current subscription",
                ]
            )

        try:
            credential = get_azure_credential()
            auth_info["status"] = "configured"
            auth_info["credential_instance"] = type(credential).__name__
        except Exception as e:
            auth_info["status"] = "error"
            auth_info["error"] = str(e)
            auth_info["recommendations"].append(f"Authentication setup failed: {e}")

        return auth_info

    async def initialize_async(
        self,
        # env_file_path: str | None = None,
        # custom_service_prefixes: dict[str, str] | None = None,
        # use_entra_id: bool = False,
    ):
        try:
            # self._settings = semantic_kernel_settings.create(
            #     env_file_path=env_file_path
            # )

            self._settings = semantic_kernel_settings(
                env_file_path=self._environment_file_path,
                custom_service_prefixes=self._custom_service_prefixes,
                use_entra_id=self._use_entra_id,
            )

        except ValidationError as ex:
            raise ServiceInitializationError(
                "Error initializing Semantic kernel settings", ex
            ) from ex

        if not self._settings.global_llm_service:
            self._settings.global_llm_service = "AzureOpenAI"

        # Initialize all discovered services
        await self._initialize_all_services()

    async def _initialize_all_services(self):
        """Initialize all discovered services during startup from Configuration"""
        if not self._settings.global_llm_service == "AzureOpenAI":
            raise ServiceInitializationError(
                "Currently supports AzureOpenAI services only"
            )

        for service_id in self._settings.get_available_services():
            try:
                await self._add_service_to_kernel(service_id)
                logging.info(
                    f"[SUCCESS] Successfully initialized service: {service_id}"
                )
            except Exception as ex:
                logging.warning(
                    f"[WARNING]  Failed to initialize service {service_id}: {ex}"
                )
                import traceback

                traceback.print_exc()

    async def _add_service_to_kernel(
        self, service_id: str, service_type: service_type = service_type.Chat_Completion
    ):
        """Add a specific service to the kernel"""
        if service_id in self.kernel.services:
            logging.info(f"Service {service_id} already exists in kernel")
            return

        config = self._settings.get_service_config(service_id)

        # async def azure_ad_token_provider() -> str:
        #     token = await DefaultAzureCredential().get_token(
        #         "https://cognitiveservices.azure.com/.default"
        #     )

        #     return token
        credential = get_azure_credential()
        token_provider = get_bearer_token_provider(
            credential, "https://cognitiveservices.azure.com/.default"
        )

        # DEBUG: Log token provider details
        logging.info(f"[DEBUG] Token provider type: {type(token_provider)}")
        logging.info(f"[DEBUG] Token provider value: {token_provider}")
        if hasattr(token_provider, "__dict__"):
            logging.info(
                f"[DEBUG] Token provider attributes: {token_provider.__dict__}"
            )

        # DEBUG: Try to call the token provider to see what it returns
        try:
            if callable(token_provider):
                # token_provider is synchronous and returns a token string directly
                token_result = token_provider()
                logging.info(
                    f"[DEBUG] Token provider result type: {type(token_result)}"
                )
                logging.info(
                    f"[DEBUG] Token provider result value: {str(token_result)[:100]}..."
                )
            else:
                logging.error("[DEBUG] Token provider is not callable!")
        except Exception as token_error:
            logging.error(f"[DEBUG] Failed to call token provider: {token_error}")

        if not config:
            raise ServiceInitializationError(
                f"No configuration found for service: {service_id}"
            )

        # if api_key doesn't exist, use ad_token_provider
        if config.api_key == "":
            # logging.info(
            #     f"[DEBUG] Creating AzureChatCompletion service with Entra ID for {service_id}"
            # )
            # logging.info(
            #     f"[DEBUG] Config: endpoint={config.endpoint}, api_version={config.api_version}, deployment={config.chat_deployment_name}"
            # )
            # # DEBUG: Log all parameter types before AzureChatCompletion creation
            # logging.info(
            #     f"[DEBUG] service_id type: {type(service_id)}, value: {service_id}"
            # )
            # logging.info(
            #     f"[DEBUG] config.endpoint type: {type(config.endpoint)}, value: {config.endpoint}"
            # )
            # logging.info(
            #     f"[DEBUG] config.api_version type: {type(config.api_version)}, value: {config.api_version}"
            # )
            # logging.info(
            #     f"[DEBUG] config.chat_deployment_name type: {type(config.chat_deployment_name)}, value: {config.chat_deployment_name}"
            # )
            # logging.info(
            #     f"[DEBUG] token_provider type: {type(token_provider)}, callable: {callable(token_provider)}"
            # )
            try:
                # service = AzureChatCompletion(
                #     service_id=str(service_id),
                #     endpoint=str(config.endpoint),
                #     api_version=str(config.api_version),
                #     deployment_name=str(config.chat_deployment_name),
                #     ad_token_provider=token_provider,
                # )
                service = AzureChatCompletion(
                    service_id=str(service_id),
                    endpoint=str(config.endpoint),
                    api_version=str(config.api_version),
                    deployment_name=str(config.chat_deployment_name),
                    ad_token_provider=token_provider,  # Pass
                )

                logging.info(
                    f"[DEBUG] AzureChatCompletion service created successfully for {service_id}"
                )
            except Exception as e:
                logging.error(
                    f"[ERROR] Failed to create AzureChatCompletion service: {e}"
                )
                logging.error(
                    f"[ERROR] Service ID: {service_id}, Endpoint: {config.endpoint}, Deployment: {config.chat_deployment_name}"
                )
                raise
        else:
            logging.info(
                f"[DEBUG] Creating AzureChatCompletion service with API key for {service_id}"
            )
            logging.info(
                f"[DEBUG] Config: endpoint={config.endpoint}, api_version={config.api_version}, deployment={config.chat_deployment_name}"
            )
            try:
                service = AzureChatCompletion(
                    service_id=str(service_id),
                    api_key=str(config.api_key),
                    endpoint=str(config.endpoint),
                    api_version=str(config.api_version),
                    deployment_name=str(config.chat_deployment_name),
                )
                logging.info(
                    f"[DEBUG] AzureChatCompletion service created successfully for {service_id}"
                )
            except Exception as e:
                logging.error(
                    f"[ERROR] Failed to create AzureChatCompletion service: {e}"
                )
                logging.error(
                    f"[ERROR] Service ID: {service_id}, Endpoint: {config.endpoint}, Deployment: {config.chat_deployment_name}"
                )
                raise
        self.kernel.add_service(service)

    def get_available_service_ids(self) -> list[str]:
        """Get list of all available service IDs"""
        return self._settings.get_available_services()

    def has_service(self, service_id: str) -> bool:
        """Check if a service is available"""
        return self._settings.has_service(service_id)

    def refresh_services(self):
        """
        Re-discover and configure all services based on current environment variables
        Useful after adding environment variables or service prefixes
        """
        self._settings.refresh_services()
        # Re-initialize services
        self._initialize_all_services()

    def get_plugin(self, plugin_name: str):
        # Check if the plugin is already added
        if plugin_name in self.kernel.plugins:
            return self.kernel.get_plugin(plugin_name)
        return None

    def get_function(self, plugin_name: str, function_name: str):
        # Check if the function is already added
        if self.get_plugin(plugin_name) is None:
            return None

        if function_name in self.kernel.plugins[plugin_name].functions:
            return self.kernel.plugins[plugin_name].functions[function_name]
        return None

    def add_plugin(
        self,
        plugin: KernelPlugin | object | dict[str, Any],
        plugin_name: str | None = None,
    ):
        # Check if the plugin is already added
        registered_plugin = self.get_plugin(plugin_name)
        if registered_plugin:
            return registered_plugin

        self.kernel.add_plugin(plugin=plugin, plugin_name=plugin_name)
        return self.kernel.get_plugin(plugin_name)

    def add_plugin_from_directory(self, parent_directory: str, plugin_name: str):
        # Check if the plugin is already added
        plugin = self.get_plugin(plugin_name)
        if plugin:
            return plugin

        self.kernel.add_plugin(
            parent_directory=parent_directory, plugin_name=plugin_name
        )
        return self.kernel.get_plugin(plugin_name)

    def add_function(
        self,
        plugin_name: str | None,
        function: KernelFunction | None = None,
        function_name: str | None = None,
        prompt_template_config: PromptTemplateConfig | None = None,
    ):
        # Check if the plugin is already added
        queried_plugin = self.get_plugin(plugin_name)
        if not queried_plugin:
            # Register the plugin
            self.add_plugin(
                plugin=KernelPlugin(name=plugin_name), plugin_name=plugin_name
            )

        # Check if the function is already added
        queried_function = self.get_function(
            # if function_name is not provided, use the function name from the function object
            function_name=function_name if function_name else function.name,
            plugin_name=plugin_name,
        )

        if queried_function:
            return queried_function

        self.kernel.add_function(
            plugin_name=plugin_name,
            function=function,
            function_name=function_name,
            prompt_template_config=prompt_template_config,
        )

        return self.kernel.get_function(
            plugin_name=plugin_name,
            function_name=function_name if function_name else function.name,
        )

    def get_azure_ai_inference_chat_completion_agent(
        self,
        agent_name: str,
        agent_instructions: str,
        service_id: str = "default",
        execution_settings: AzureAIInferenceChatPromptExecutionSettings | None = None,
        plugins: list[KernelPlugin | object | dict[str, Any]] | None = None,
    ):
        # Ensure the service is available and added to kernel
        if not self.has_service(service_id):
            raise ServiceInitializationError(
                f"Service '{service_id}' not available. Available services: {self.get_available_service_ids()}"
            )

        # Get the service configuration for creating the agent
        # config = self._settings.get_service_config(service_id)

        if not execution_settings:
            execution_settings = AzureAIInferenceChatPromptExecutionSettings(
                service_id=service_id,
                extra_parameters={
                    "reasoning_effort": "high"
                },  # Increased from medium to improve JSON return rate
                # SECURITY: Limit auto-invocations per turn to prevent runaway tool execution
                function_choice_behavior=FunctionChoiceBehavior.Auto(
                    maximum_auto_invoke_attempts=5
                ),
            )

        agent = ChatCompletionAgent(
            service=self.kernel.get_service(service_id),
            name=agent_name,
            instructions=agent_instructions,
            arguments=KernelArguments(
                settings=execution_settings,
            ),
            plugins=plugins,
        )
        return agent

    async def get_azure_chat_completion_agent(
        self,
        agent_name: str,
        agent_system_prompt: str | None = None,
        agent_instructions: str | None = None,
        agent_description: str | None = None,
        service_id: str = "default",
        execution_settings: AzureChatPromptExecutionSettings | None = None,
        plugins: list[KernelPlugin | object | dict[str, Any]] | None = None,
    ):
        # Ensure the service is available and added to kernel
        if not self.has_service(service_id):
            raise ServiceInitializationError(
                f"Service '{service_id}' not available. Available services: {self.get_available_service_ids()}"
            )

        # Get or add the service to kernel
        # self.get_kernel(
        #     service_id=service_id, service_type=service_type.Chat_Completion
        # )

        # Get the service configuration for creating the agent
        # config = self._settings.get_service_config(service_id)

        if not execution_settings:
            # CRITICAL: Apply strict token limits to prevent 428K token errors
            execution_settings = AzureChatPromptExecutionSettings(
                service_id=service_id,
                temperature=1.0,  # O3 model only supports temperature=1.0
                reasoning_effort="high",  # Increased from medium to improve JSON return rate
            )

        if service_id == "GPT5" or service_id == "default":
            # Use GPT-5 specific settings with strict token limits
            execution_settings = AzureChatPromptExecutionSettings(
                service_id=service_id,
                temperature=1.0,  # O3 model only supports temperature=1.0
                reasoning_effort="high",
                # timeout configuration
                timeout=120,  # 2mins
                max_retries=5,
            )

        ##########################################################################
        # Add Agent Level max token setting
        ##########################################################################
        # AGENT-SPECIFIC TOKEN CONTROL: Balance between preventing hallucination and allowing meaningful responses

        # if agent_name:
        #     agent_name_lower = agent_name.lower()

        #     # TECHNICAL WRITER AGENTS: Different limits based on phase
        #     if "technical_writer" in agent_name_lower:
        #         # Check if this is the Documentation phase (stricter but not too restrictive)
        #         if agent_instructions and "documentation" in agent_instructions.lower():
        #             execution_settings.max_completion_tokens = (
        #                 2500  # DOCUMENTATION: Strict but allows meaningful reports
        #             )
        #             logging.info(
        #                 f"[TOKEN_CONTROL] Technical Writer '{agent_name}' in Documentation phase limited to 2500 tokens - forces file verification but allows reports"
        #             )
        #         else:
        #             execution_settings.max_completion_tokens = (
        #                 2000  # OTHER PHASES: Room for analysis and documentation
        #             )
        #             logging.info(
        #                 f"[TOKEN_CONTROL] Technical Writer '{agent_name}' limited to 2000 tokens - balanced approach"
        #             )

        #     # YAML EXPERT AGENTS: Need substantial space for complex YAML generation
        #     elif "yaml_expert" in agent_name_lower:
        #         execution_settings.max_completion_tokens = (
        #             2500  # YAML: Complex file generation and explanations
        #         )
        #         logging.info(
        #             f"[TOKEN_CONTROL] YAML Expert '{agent_name}' allocated 2500 tokens - complex file operations"
        #         )

        #     # AZURE EXPERT AGENTS: Moderate limits for comprehensive analysis
        #     elif "azure_expert" in agent_name_lower:
        #         execution_settings.max_completion_tokens = (
        #             2500  # AZURE: Detailed analysis + recommendations
        #         )
        #         logging.info(
        #             f"[TOKEN_CONTROL] Azure Expert '{agent_name}' limited to 2500 tokens - comprehensive analysis"
        #         )

        #     # EKS/GKE EXPERT AGENTS: Moderate limits for source analysis
        #     elif any(
        #         expert in agent_name_lower for expert in ["eks_expert", "gke_expert"]
        #     ):
        #         execution_settings.max_completion_tokens = (
        #             1800  # SOURCE: Detailed source analysis
        #         )
        #         logging.info(
        #             f"[TOKEN_CONTROL] Source Expert '{agent_name}' limited to 1800 tokens - detailed analysis"
        #         )

        #     # Chief Architect: Higher limits for coordination and oversight
        #     elif "technical_architect" in agent_name_lower:
        #         execution_settings.max_completion_tokens = (
        #             2500  # COORDINATION: Comprehensive oversight
        #         )
        #         logging.info(
        #             f"[TOKEN_CONTROL] Chief Architect '{agent_name}' allocated 2500 tokens - coordination role"
        #         )

        #     # QA ENGINEER: Moderate limits for thorough validation
        #     elif "qa_engineer" in agent_name_lower:
        #         execution_settings.max_completion_tokens = (
        #             2500  # VALIDATION: Thorough testing reports
        #         )
        #         logging.info(
        #             f"[TOKEN_CONTROL] QA Engineer '{agent_name}' limited to 2500 tokens - validation reports"
        #         )

        #     # INCIDENT RESPONSE: Higher limits for comprehensive incident analysis
        #     elif "incident_response" in agent_name_lower:
        #         execution_settings.max_completion_tokens = (
        #             2000  # RECOVERY: Comprehensive incident handling
        #         )
        #         logging.info(
        #             f"[TOKEN_CONTROL] Incident Response '{agent_name}' allocated 2000 tokens - incident analysis"
        #         )

        #     # DEFAULT: Keep reasonable baseline for unknown agents
        #     else:
        #         execution_settings.max_completion_tokens = (
        #             1500  # DEFAULT: Balanced baseline
        #         )
        #         logging.info(
        #             f"[TOKEN_CONTROL] Unknown agent type '{agent_name}' using default 1500 tokens"
        #         )

        # service: AzureChatCompletion = self.kernel.get_service(service_id)
        new_agent = ChatCompletionAgent(
            service=self.kernel.get_service(service_id),
            name=agent_name,
            instructions=agent_instructions,
            description=agent_description,
            arguments=KernelArguments(
                settings=execution_settings,
            ),
            plugins=plugins,
        )
        return new_agent

        # new_agent = ChatCompletionAgent(
        #     service=AzureChatCompletion(
        #         service_id=service_id,
        #         api_key=config.api_key,
        #         endpoint=config.endpoint,
        #         api_version=config.api_version,
        #         deployment_name=config.chat_deployment_name,
        #     ),
        #     name=agent_name,
        #     instructions=agent_instructions,
        #     arguments=KernelArguments(
        #         settings=execution_settings,
        #     ),
        #     plugins=plugins,
        # )
        # return new_agent

    async def get_azure_ai_agent(
        self,
        agent_name: str,
        instructions: str,
        plugins: list[KernelPlugin | object | dict[str, Any]] | None = None,
        agent_id: str | None = None,
    ):
        if not self._settings.global_llm_service == "AzureOpenAI":
            raise ServiceInitializationError("Supports AzureOpenAI only")

        # Using explicit async credential following Semantic Kernel v1.36.0+ best practices
        credential = get_async_azure_credential()
        client = AzureAIAgent.create_client(credential=credential)
        agent_definition: AzureAIAgent | None = None

        if agent_id:
            # Check if the agent is already added
            try:
                agent_definition = await client.agents.get_agent(agent_id)
            except Exception:
                # Create a new agent
                agent_definition = await client.agents.create_agent(
                    model=AzureAIAgentSettings().model_deployment_name,
                    name=agent_name,
                    instructions=instructions,
                )
                logging.info(
                    f"Agent is not found. \nCreating new agent with name: {agent_name}, agent_id: {agent_definition.id}"
                )
        else:
            logging.info(
                f"Creating new agent with name: {agent_name}, agent_id: {agent_id}"
            )
            # Create a new agent
            agent_definition = await client.agents.create_agent(
                model=AzureAIAgentSettings().model_deployment_name,
                name=agent_name,
                instructions=instructions,
            )

        agent = AzureAIAgent(
            client=client, definition=agent_definition, plugins=plugins
        )

        return agent

    async def get_azure_assistant_agent(self, agent_name: str, agent_instructions: str):
        # Using updated credential utility with timeout protection
        credential = get_azure_credential()
        client, model = AzureAssistantAgent.setup_resources(
            ad_token_provider=get_bearer_token_provider(
                credential, "https://cognitiveservices.azure.com/.default"
            ),
            env_file_path=self._settings.env_file_path,
        )
        definition = await client.beta.assistants.create(
            model=model, instructions=agent_instructions, name=agent_name
        )
        return AzureAssistantAgent(
            client=client,
            definition=definition,
        )

    def get_prompt_execution_settings_from_service_id(self, service_id: str):
        return self.kernel.get_prompt_execution_settings_from_service_id(service_id)
