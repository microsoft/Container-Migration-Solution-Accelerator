"""Tests for libs/base/kernel_agent.py."""

import importlib
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, ValidationError
from semantic_kernel.exceptions.service_exceptions import ServiceInitializationError

# `libs/base/SKBase.py` is currently empty in the repository, but
# `libs/base/kernel_agent.py` (and the orphaned `SKLogicBase.py`) import
# `SKBaseModel` from it. Neither file is imported by production code, so the
# missing symbol does not surface at runtime today. To exercise `kernel_agent`
# in isolation we inject a minimal stand-in into the namespace before the
# module is imported. This intentionally does NOT modify any production source
# file (out of scope for this PR); it is a test-only shim with idempotent
# `hasattr` guard, so it is a no-op once `SKBase` defines `SKBaseModel` for real.
import libs.base.SKBase as _skbase_mod  # noqa: E402

if not hasattr(_skbase_mod, "SKBaseModel"):

    class _SKBaseModelStub(BaseModel):
        model_config = {"arbitrary_types_allowed": True}

    _skbase_mod.SKBaseModel = _SKBaseModelStub  # type: ignore[attr-defined]
    # Drop any previously-cached import of kernel_agent so its `from
    # libs.base.SKBase import SKBaseModel` line picks up the stub on first
    # import below.
    sys.modules.pop("libs.base.kernel_agent", None)

importlib.import_module("libs.base.kernel_agent")  # noqa: E402


@pytest.fixture
def patched():
    with (
        patch("libs.base.kernel_agent.Kernel") as kernel_cls,
        patch("libs.base.kernel_agent.Configuration") as cfg_cls,
        patch("libs.base.kernel_agent.AzureChatCompletion") as chat_cls,
        patch("libs.base.kernel_agent.AzureTextCompletion") as text_cls,
    ):
        kernel = MagicMock()
        kernel.plugins = {}
        kernel.services = {}
        kernel_cls.return_value = kernel
        cfg = SimpleNamespace(global_llm_service="AzureOpenAI", env_file_path=None)
        cfg_cls.return_value = cfg
        yield {
            "kernel_cls": kernel_cls,
            "kernel": kernel,
            "cfg_cls": cfg_cls,
            "cfg": cfg,
            "chat_cls": chat_cls,
            "text_cls": text_cls,
        }


class TestInit:
    def test_init_sets_kernel_and_settings(self, patched):
        from libs.base.kernel_agent import semantic_kernel_agent

        a = semantic_kernel_agent()
        assert a.kernel is patched["kernel"]
        assert a._settings is patched["cfg"]

    def test_init_with_env_file_path(self, patched):
        from libs.base.kernel_agent import semantic_kernel_agent

        semantic_kernel_agent(env_file_path="some/path.env")
        patched["cfg_cls"].assert_called_with(env_file_path="some/path.env")

    def test_init_default_global_llm_service(self, patched):
        from libs.base.kernel_agent import semantic_kernel_agent

        patched["cfg"].global_llm_service = None
        a = semantic_kernel_agent()
        assert a._settings.global_llm_service == "AzureOpenAI"

    def test_init_validation_error_wraps(self, patched):
        from libs.base.kernel_agent import semantic_kernel_agent

        # Construct a real ValidationError via a Pydantic model
        try:
            from pydantic import BaseModel

            class _M(BaseModel):
                x: int

            _M(x="not-int")
        except ValidationError as ve:
            patched["cfg_cls"].side_effect = ve
        with pytest.raises(ServiceInitializationError):
            semantic_kernel_agent()


class TestPlugins:
    def test_get_plugin_present(self, patched):
        from libs.base.kernel_agent import semantic_kernel_agent

        a = semantic_kernel_agent()
        a.kernel.plugins = {"p": MagicMock(name="plug")}
        a.kernel.get_plugin = MagicMock(return_value="plug-obj")
        assert a.get_plugin("p") == "plug-obj"

    def test_get_plugin_missing(self, patched):
        from libs.base.kernel_agent import semantic_kernel_agent

        a = semantic_kernel_agent()
        a.kernel.plugins = {}
        assert a.get_plugin("nope") is None

    def test_add_plugin_when_present_returns_existing(self, patched):
        from libs.base.kernel_agent import semantic_kernel_agent

        a = semantic_kernel_agent()
        a.kernel.plugins = {"p": "x"}
        a.kernel.get_plugin = MagicMock(return_value="existing")
        result = a.add_plugin(plugin=MagicMock(), plugin_name="p")
        assert result == "existing"
        a.kernel.add_plugin.assert_not_called()

    def test_add_plugin_when_absent_adds(self, patched):
        from libs.base.kernel_agent import semantic_kernel_agent

        a = semantic_kernel_agent()
        a.kernel.plugins = {}
        a.kernel.get_plugin = MagicMock(return_value="newly")
        plug = MagicMock()
        result = a.add_plugin(plugin=plug, plugin_name="p")
        a.kernel.add_plugin.assert_called_once_with(plugin=plug, plugin_name="p")
        assert result == "newly"

    def test_add_plugin_from_directory_present(self, patched):
        from libs.base.kernel_agent import semantic_kernel_agent

        a = semantic_kernel_agent()
        a.kernel.plugins = {"p": MagicMock()}
        a.kernel.get_plugin = MagicMock(return_value="existing")
        assert a.add_plugin_from_directory("/dir", "p") == "existing"
        a.kernel.add_plugin.assert_not_called()

    def test_add_plugin_from_directory_absent(self, patched):
        from libs.base.kernel_agent import semantic_kernel_agent

        a = semantic_kernel_agent()
        a.kernel.plugins = {}
        a.kernel.get_plugin = MagicMock(return_value="newly")
        result = a.add_plugin_from_directory("/dir", "p")
        a.kernel.add_plugin.assert_called_once_with(
            parent_directory="/dir", plugin_name="p"
        )
        assert result == "newly"


class TestFunctions:
    def test_get_function_no_plugin(self, patched):
        from libs.base.kernel_agent import semantic_kernel_agent

        a = semantic_kernel_agent()
        a.kernel.plugins = {}
        assert a.get_function("p", "f") is None

    def test_get_function_present(self, patched):
        from libs.base.kernel_agent import semantic_kernel_agent

        a = semantic_kernel_agent()
        plug = MagicMock()
        plug.functions = {"f": "func-obj"}
        a.kernel.plugins = {"p": plug}
        a.kernel.get_plugin = MagicMock(return_value=plug)
        assert a.get_function("p", "f") == "func-obj"

    def test_get_function_function_missing(self, patched):
        from libs.base.kernel_agent import semantic_kernel_agent

        a = semantic_kernel_agent()
        plug = MagicMock()
        plug.functions = {}
        a.kernel.plugins = {"p": plug}
        a.kernel.get_plugin = MagicMock(return_value=plug)
        assert a.get_function("p", "f") is None

    def test_add_function_existing(self, patched):
        from libs.base.kernel_agent import semantic_kernel_agent

        a = semantic_kernel_agent()
        plug = MagicMock()
        plug.functions = {"f": "existing-func"}
        a.kernel.plugins = {"p": plug}
        a.kernel.get_plugin = MagicMock(return_value=plug)
        result = a.add_function(plugin_name="p", function_name="f", function=MagicMock())
        assert result == "existing-func"
        a.kernel.add_function.assert_not_called()

    def test_add_function_new(self, patched):
        from libs.base.kernel_agent import semantic_kernel_agent

        a = semantic_kernel_agent()
        # First call: no plugin -> add_plugin path; then get_function returns None; then add
        a.kernel.plugins = {}

        # Track plugin presence dynamically
        state = {"plugin": None}

        def get_plugin_side(name):
            return state["plugin"]

        a.kernel.get_plugin = MagicMock(side_effect=get_plugin_side)

        def add_plugin_side(plugin, plugin_name):
            plug = MagicMock()
            plug.functions = {}
            state["plugin"] = plug
            a.kernel.plugins[plugin_name] = plug

        a.kernel.add_plugin.side_effect = add_plugin_side
        a.kernel.get_function = MagicMock(return_value="new-func")

        fn = MagicMock()
        fn.name = "f"
        result = a.add_function(plugin_name="p", function=fn)
        a.kernel.add_function.assert_called_once()
        assert result == "new-func"


class TestGetKernel:
    def test_get_kernel_chat_adds_service(self, patched):
        from libs.base.kernel_agent import semantic_kernel_agent, service_type

        a = semantic_kernel_agent()
        a.kernel.services = {}
        result = a.get_kernel(service_id="default", service_type=service_type.Chat_Completion)
        a.kernel.add_service.assert_called_once()
        assert result is a.kernel

    def test_get_kernel_already_present(self, patched):
        from libs.base.kernel_agent import semantic_kernel_agent

        a = semantic_kernel_agent()
        a.kernel.services = {"default": object()}
        result = a.get_kernel(service_id="default")
        a.kernel.add_service.assert_not_called()
        assert result is a.kernel

    def test_get_kernel_non_azure_raises(self, patched):
        from libs.base.kernel_agent import semantic_kernel_agent

        a = semantic_kernel_agent()
        a._settings.global_llm_service = "OpenAI"
        with pytest.raises(ServiceInitializationError):
            a.get_kernel()

    def test_get_prompt_execution_settings(self, patched):
        from libs.base.kernel_agent import semantic_kernel_agent

        a = semantic_kernel_agent()
        a.kernel.get_prompt_execution_settings_from_service_id = MagicMock(
            return_value="settings"
        )
        assert a.get_prompt_execution_settings_from_service_id("svc") == "settings"


class TestServiceTypeEnum:
    def test_enum_values(self, patched):
        from libs.base.kernel_agent import service_type

        assert service_type.Chat_Completion.value == "ChatCompletion"
        assert service_type.Text_Completion.value == "TextCompletion"
