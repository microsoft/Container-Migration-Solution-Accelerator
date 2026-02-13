# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from abc import ABC

from libs.agent_framework.agent_framework_helper import AgentFrameworkHelper
from libs.application.application_context import AppContext


class AgentBase(ABC):
    """Base class for all agents."""

    def __init__(self, app_context: AppContext | None = None):
        if app_context is None:
            raise ValueError("AppContext must be provided to initialize Agent_Base.")

        self.app_context: AppContext = app_context

        if self.app_context.is_registered(AgentFrameworkHelper):
            self.agent_framework_helper: AgentFrameworkHelper = (
                self.app_context.get_service(AgentFrameworkHelper)
            )
        else:
            raise ValueError(
                "AgentFrameworkHelper is not registered in the AppContext."
            )
