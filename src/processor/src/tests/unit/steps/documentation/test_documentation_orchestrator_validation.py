# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio

import pytest

from libs.agent_framework.agent_framework_helper import AgentFrameworkHelper
from steps.convert.models.step_output import Yaml_ExtendedBooleanResult
from steps.documentation.orchestration.documentation_orchestrator import (
    DocumentationOrchestrator,
)


class _FakeAgentFrameworkHelper:
    pass


class _FakeAppContext:
    def __init__(self):
        self._helper = _FakeAgentFrameworkHelper()

    def is_registered(self, service_type) -> bool:
        return service_type is AgentFrameworkHelper

    def get_service(self, service_type):
        if service_type is AgentFrameworkHelper:
            return self._helper
        raise KeyError(service_type)


def test_documentation_orchestrator_rejects_none_task_param():
    async def _run():
        orch = DocumentationOrchestrator(app_context=_FakeAppContext())
        with pytest.raises(ValueError, match=r"task_param cannot be None"):
            await orch.execute(None)

    asyncio.run(_run())


def test_documentation_orchestrator_requires_process_id():
    async def _run():
        orch = DocumentationOrchestrator(app_context=_FakeAppContext())
        msg = Yaml_ExtendedBooleanResult(process_id=None)
        with pytest.raises(ValueError, match=r"process_id is required"):
            await orch.execute(msg)

    asyncio.run(_run())
