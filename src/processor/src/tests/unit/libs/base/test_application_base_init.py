# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Coverage for libs/base/application_base.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _build_concrete():
    """Define a minimal concrete subclass to satisfy abstractmethods."""
    from libs.base.application_base import ApplicationBase

    class _App(ApplicationBase):
        def initialize(self):
            return None

        async def run(self):
            return None

    return _App


@pytest.fixture
def patches_chain():
    """Patch every external dep of ApplicationBase.__init__."""
    with patch("libs.base.application_base.load_dotenv") as load_dotenv, \
         patch("libs.base.application_base.DefaultAzureCredential") as cred, \
         patch("libs.base.application_base._envConfiguration") as env_cfg, \
         patch("libs.base.application_base.AppConfigurationHelper") as ac_helper, \
         patch("libs.base.application_base.Configuration") as config, \
         patch("libs.base.application_base.AgentFrameworkSettings") as afs, \
         patch("libs.base.application_base.logging.basicConfig") as basic_config:
        env_cfg_inst = env_cfg.return_value
        env_cfg_inst.app_configuration_url = None
        cfg_instance = MagicMock()
        cfg_instance.app_logging_enable = False
        config.return_value = cfg_instance
        yield {
            "load_dotenv": load_dotenv,
            "cred": cred,
            "env_cfg": env_cfg,
            "ac_helper": ac_helper,
            "config": config,
            "afs": afs,
            "basic_config": basic_config,
            "config_instance": cfg_instance,
        }


class TestApplicationBaseInit:
    def test_init_with_explicit_env_path_skips_app_config(self, patches_chain, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("X=1")
        _App = _build_concrete()
        app = _App(env_file_path=str(env_file))
        # load_dotenv called with explicit path
        patches_chain["load_dotenv"].assert_called_once()
        # AppConfigurationHelper not used (URL is None)
        patches_chain["ac_helper"].assert_not_called()
        # Settings + credential set
        assert app.application_context is not None
        patches_chain["afs"].assert_called_once()

    def test_init_loads_app_config_when_url_set(self, patches_chain, tmp_path):
        patches_chain["env_cfg"].return_value.app_configuration_url = "https://x.azconfig.io"
        env_file = tmp_path / ".env"
        env_file.write_text("X=1")
        _App = _build_concrete()
        _App(env_file_path=str(env_file))
        patches_chain["ac_helper"].assert_called_once()
        # The helper instance had its method invoked
        helper_instance = patches_chain["ac_helper"].return_value
        helper_instance.read_and_set_environmental_variables.assert_called_once()

    def test_init_enables_logging(self, patches_chain, tmp_path):
        patches_chain["config_instance"].app_logging_enable = True
        patches_chain["config_instance"].app_logging_level = "INFO"
        env_file = tmp_path / ".env"
        env_file.write_text("X=1")
        _App = _build_concrete()
        _App(env_file_path=str(env_file))
        patches_chain["basic_config"].assert_called_once()

    def test_init_without_env_path_derives_location(self, patches_chain):
        _App = _build_concrete()
        # Without explicit path, _load_env -> _get_derived_class_location() -> inspect.getfile(self.__class__)
        # On _App defined here, inspect.getfile returns this test's path. load_dotenv gets that adjacent .env.
        with patch("libs.base.application_base.os.path.join", return_value="/tmp/derived/.env"), \
             patch("libs.base.application_base.os.path.dirname", return_value="/tmp/derived"):
            _App()
        patches_chain["load_dotenv"].assert_called_once()


class TestLoadEnvDirect:
    def test_explicit_path_returns_path(self, patches_chain, tmp_path):
        _App = _build_concrete()
        app = _App.__new__(_App)
        result = app._load_env(env_file_path=str(tmp_path / ".env"))
        assert result == str(tmp_path / ".env")

    def test_no_path_derives_via_class(self, patches_chain):
        _App = _build_concrete()
        app = _App.__new__(_App)
        result = app._load_env()
        # Should return derived .env path
        assert result.endswith(".env")


class TestDerivedClassLocation:
    def test_returns_file_path(self):
        _App = _build_concrete()
        app = _App.__new__(_App)
        result = app._get_derived_class_location()
        # inspect.getfile returns this test module path
        assert result.endswith(".py")
