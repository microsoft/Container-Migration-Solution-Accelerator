# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Coverage tests for libs.base.application_base.ApplicationBase."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from libs.base import application_base as ab_module
from libs.base.application_base import ApplicationBase


class _ConcreteApp(ApplicationBase):
    """Minimal concrete subclass so we can instantiate ApplicationBase."""

    def run(self):  # pragma: no cover - never invoked, abstract impl satisfied
        return None

    def initialize(self):  # pragma: no cover - never invoked
        return None


def _patch_dependencies(app_config_url=None, logging_enabled=False, level="INFO"):
    """(Unused helper kept for reference.)"""
    return None



def test_run_and_initialize_must_be_implemented():
    with pytest.raises(NotImplementedError):
        ApplicationBase.run(MagicMock())
    with pytest.raises(NotImplementedError):
        ApplicationBase.initialize(MagicMock())


def test_constructor_skips_app_config_when_url_empty(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("KEY=VAL")

    cfg_obj = SimpleNamespace(app_logging_enable=False, app_logging_level="INFO")
    env_cfg = SimpleNamespace(app_configuration_url="")

    with (
        patch.object(ab_module, "DefaultAzureCredential", return_value=MagicMock()),
        patch.object(ab_module, "_envConfiguration", return_value=env_cfg),
        patch.object(ab_module, "Configuration", return_value=cfg_obj),
        patch.object(ab_module, "AppConfigurationHelper") as ach,
        patch.object(ab_module, "AgentFrameworkSettings", return_value=MagicMock()),
        patch.object(ab_module, "load_dotenv"),
    ):
        app = _ConcreteApp(env_file_path=str(env_file))
        ach.assert_not_called()
    assert app.application_context is not None
    assert app.application_context.configuration is cfg_obj


def test_constructor_loads_app_configuration_when_url_present(tmp_path):
    cfg_obj = SimpleNamespace(app_logging_enable=False, app_logging_level="INFO")
    env_cfg = SimpleNamespace(app_configuration_url="https://my-config")

    with (
        patch.object(ab_module, "DefaultAzureCredential", return_value=MagicMock()),
        patch.object(ab_module, "_envConfiguration", return_value=env_cfg),
        patch.object(ab_module, "Configuration", return_value=cfg_obj),
        patch.object(ab_module, "AppConfigurationHelper") as ach,
        patch.object(ab_module, "AgentFrameworkSettings", return_value=MagicMock()),
        patch.object(ab_module, "load_dotenv"),
    ):
        _ConcreteApp(env_file_path=str(tmp_path / ".env"))
        ach.assert_called_once()
        ach.return_value.read_and_set_environmental_variables.assert_called_once()


def test_constructor_enables_logging_when_configured(tmp_path):
    cfg_obj = SimpleNamespace(app_logging_enable=True, app_logging_level="DEBUG")
    env_cfg = SimpleNamespace(app_configuration_url=None)

    with (
        patch.object(ab_module, "DefaultAzureCredential", return_value=MagicMock()),
        patch.object(ab_module, "_envConfiguration", return_value=env_cfg),
        patch.object(ab_module, "Configuration", return_value=cfg_obj),
        patch.object(ab_module, "AppConfigurationHelper"),
        patch.object(ab_module, "AgentFrameworkSettings", return_value=MagicMock()),
        patch.object(ab_module, "load_dotenv"),
        patch.object(ab_module.logging, "basicConfig") as basic_cfg,
    ):
        _ConcreteApp(env_file_path=str(tmp_path / ".env"))
        basic_cfg.assert_called_once()


def test_load_env_uses_provided_path(tmp_path):
    env_file = tmp_path / "custom.env"
    env_file.write_text("X=Y")
    instance = _ConcreteApp.__new__(_ConcreteApp)
    with patch.object(ab_module, "load_dotenv") as ld:
        result = instance._load_env(env_file_path=str(env_file))
    assert result == str(env_file)
    ld.assert_called_once_with(dotenv_path=str(env_file))


def test_load_env_derives_path_from_class_location(tmp_path):
    instance = _ConcreteApp.__new__(_ConcreteApp)
    fake_location = str(tmp_path / "subclass.py")
    with (
        patch.object(
            _ConcreteApp,
            "_get_derived_class_location",
            return_value=fake_location,
        ),
        patch.object(ab_module, "load_dotenv") as ld,
    ):
        result = instance._load_env()
    expected = os.path.join(os.path.dirname(fake_location), ".env")
    assert result == expected
    ld.assert_called_once_with(dotenv_path=expected)


def test_get_derived_class_location_uses_inspect():
    instance = _ConcreteApp.__new__(_ConcreteApp)
    location = instance._get_derived_class_location()
    assert location.endswith("test_application_base.py")
