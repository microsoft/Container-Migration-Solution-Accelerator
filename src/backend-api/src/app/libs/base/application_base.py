# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import inspect
import logging
import os
from abc import ABC, abstractmethod

from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from libs.application.application_configuration import (
    Configuration,
    _envConfiguration,
)
from libs.application.application_context import AppContext
from libs.azure.app_configuration import AppConfigurationHelper


class Application_Base(ABC):
    application_context: AppContext = None

    @abstractmethod
    def run(self):
        raise NotImplementedError("The run method must be implemented by subclasses.")

    @abstractmethod
    def initialize(self):
        raise NotImplementedError(
            "The initialize method must be implemented by subclasses."
        )

    def __init__(self, env_file_path: str | None = None, **data):
        super().__init__(**data)

        # Read .env file first - Get App configuration Service Endpoint
        self._load_env(env_file_path=env_file_path)

        # Set App Context object
        self.application_context = AppContext()
        # Set Default Azure Credential to the application context
        self.application_context.set_credential(DefaultAzureCredential())

        # Get App Configuration Endpoint from .env file
        app_config_url: str | None = _envConfiguration().app_configuration_url
        # Load environment variables from Azure App Configuration endpoint url
        if app_config_url != "" and app_config_url is not None:
            # If app_configuration_url is not None, then read the configuration from Azure App Configuration
            # and set them as environment variables
            AppConfigurationHelper(
                app_configuration_url=app_config_url,
                credential=self.application_context.credential,
            ).read_and_set_environmental_variables()

        self.application_context.set_configuration(Configuration())

        if self.application_context.configuration.app_logging_enable:
            # Read Configuration for Logging Level as a Text then retrive the logging level
            logging_level = getattr(
                logging, self.application_context.configuration.app_logging_level
            )
            logging.basicConfig(level=logging_level)

            # Configure Azure package logging levels only if packages are specified
            if self.application_context.configuration.azure_logging_packages:
                azure_level = getattr(logging, self.application_context.configuration.azure_package_logging_level.upper(), logging.WARNING)
                for logger_name in filter(None, (pkg.strip() for pkg in self.application_context.configuration.azure_logging_packages.split(','))):
                    logging.getLogger(logger_name).setLevel(azure_level)

        # Initialize the application
        self.initialize()

    def _load_env(self, env_file_path: str | None = None):
        # if .env file path is provided, load it
        # else derive the path from the derived class location
        # or Environment variable in OS will be loaded by appplication_coonfiguration.py with using pydentic_settings, BaseSettings
        if env_file_path:
            load_dotenv(dotenv_path=env_file_path)
            return env_file_path

        derived_class_location = self._get_derived_class_location()
        env_file_path = os.path.join(os.path.dirname(derived_class_location), ".env")
        load_dotenv(dotenv_path=env_file_path)
        return env_file_path

    def _get_derived_class_location(self):
        return inspect.getfile(self.__class__)
