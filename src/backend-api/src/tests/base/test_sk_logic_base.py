"""Tests for libs/base/SKLogicBase.py.

The production module imports ``SKBaseModel`` from ``libs.base.SKBase`` (which
is empty in this repo) and ``semantic_kernel_agent`` from
``libs.base.KernelAgent`` (a module that does not exist on disk; the actual
file is ``kernel_agent.py``). Stub both before importing so the module is
exercised without modifying production source.
"""

import importlib
import sys
import types
from typing import Type
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Module-load helpers (stub SKBaseModel and the misspelled KernelAgent module)
# ---------------------------------------------------------------------------
import libs.base.SKBase as _skbase_mod  # noqa: E402


class _SKBaseModelStub(BaseModel):
    # ``extra="allow"`` is required because SKLogicBase.__init__ sets
    # attributes (``response_format``, ``system_prompt``) that are not
    # declared as Pydantic fields.
    model_config = {
        "arbitrary_types_allowed": True,
        "extra": "allow",
    }


# Always force-set our stub so it overrides whatever a previously-loaded
# test module installed (e.g. test_kernel_agent.py uses a stricter stub
# without ``extra="allow"`` which prevents SKLogicBase from being constructed).
_skbase_mod.SKBaseModel = _SKBaseModelStub  # type: ignore[attr-defined]

# Ensure libs.base.kernel_agent has been imported (creates real
# semantic_kernel_agent symbol used by the stub below).
import libs.base.kernel_agent as _kernel_agent_mod  # noqa: E402

if "libs.base.KernelAgent" not in sys.modules:
    _stub_kernel_agent_module = types.ModuleType("libs.base.KernelAgent")
    _stub_kernel_agent_module.semantic_kernel_agent = (
        _kernel_agent_mod.semantic_kernel_agent
    )
    sys.modules["libs.base.KernelAgent"] = _stub_kernel_agent_module

# Now safe to import the SUT.
sk_logic_base = importlib.import_module("libs.base.SKLogicBase")
SKLogicBase = sk_logic_base.SKLogicBase


class _Resp(BaseModel):
    name: str = "x"


class _ConcreteLogic(SKLogicBase):
    """A concrete subclass that satisfies abstract methods without doing real work."""

    def _init_agent(self):  # override: skip real agent setup
        return None

    async def _init_agent_async(self):
        return None

    async def execute_thread(  # type: ignore[override]
        self, user_input, response_format=None, thread=None
    ):
        return ("answer", thread)


class _BareLogic(SKLogicBase):
    """Subclass that delegates _init_agent / _init_agent_async to base.

    Used to exercise the NotImplementedError branches without reaching
    the abstract execute_thread.
    """

    def _init_agent(self):  # call up to base to hit raise
        return super()._init_agent()

    async def _init_agent_async(self):
        return await super()._init_agent_async()

    async def execute_thread(self, *a, **kw):  # satisfy abstractmethod
        return None


def _make_kernel_agent_stub():
    """Build a MagicMock that behaves enough like a semantic_kernel_agent."""
    return MagicMock()


class TestValidateResponseFormat:
    def test_returns_true_when_none(self):
        assert SKLogicBase._validate_response_format(None) is True

    def test_returns_true_for_basemodel_subclass(self):
        assert SKLogicBase._validate_response_format(_Resp) is True

    def test_raises_typeerror_when_not_a_class(self):
        with pytest.raises(TypeError):
            SKLogicBase._validate_response_format("not-a-class")

    def test_raises_typeerror_when_not_basemodel(self):
        class _Plain:
            pass

        with pytest.raises(TypeError):
            SKLogicBase._validate_response_format(_Plain)


class TestConstruction:
    def test_concrete_subclass_instantiates(self):
        ka = _make_kernel_agent_stub()
        instance = _ConcreteLogic(kernel_agent=ka)
        assert instance.kernel_agent is ka

    def test_constructor_passes_through_response_format_and_prompt(self):
        ka = _make_kernel_agent_stub()
        instance = _ConcreteLogic(
            kernel_agent=ka,
            system_prompt="be helpful",
            response_format=_Resp,
        )
        assert instance.kernel_agent is ka
        # response_format / system_prompt are set as instance attrs (not declared
        # Pydantic fields) — confirm they exist via the underlying dict.
        assert getattr(instance, "response_format") is _Resp
        assert getattr(instance, "system_prompt") == "be helpful"


class TestNotImplementedBranches:
    def test_init_agent_raises_in_base(self):
        ka = _make_kernel_agent_stub()
        with pytest.raises(NotImplementedError):
            _BareLogic(kernel_agent=ka)

    @pytest.mark.asyncio
    async def test_init_agent_async_raises_in_base(self):
        # Build with no-op init to skip _init_agent failure, then invoke
        # _init_agent_async via super() to hit the base raise.
        ka = _make_kernel_agent_stub()

        class _OnlyAsyncRaises(SKLogicBase):
            def _init_agent(self):  # no-op so __init__ works
                return None

            async def _init_agent_async(self):
                return await super()._init_agent_async()

            async def execute_thread(self, *a, **kw):
                return None

        instance = _OnlyAsyncRaises(kernel_agent=ka)
        with pytest.raises(NotImplementedError):
            await instance._init_agent_async()

    @pytest.mark.asyncio
    async def test_execute_raises_not_implemented(self):
        ka = _make_kernel_agent_stub()
        instance = _ConcreteLogic(kernel_agent=ka)
        with pytest.raises(NotImplementedError):
            await instance.execute({"x": 1})


class TestCreateClassMethod:
    @pytest.mark.asyncio
    async def test_create_calls_init_agent_async(self):
        ka = _make_kernel_agent_stub()

        captured = {"called": False}

        class _Tracking(SKLogicBase):
            def _init_agent(self):
                return None

            async def _init_agent_async(self):
                captured["called"] = True

            async def execute_thread(self, *a, **kw):
                return None

        instance = await _Tracking.create(kernel_agent=ka)
        assert isinstance(instance, _Tracking)
        assert captured["called"] is True


class TestAbstractContract:
    def test_cannot_instantiate_abstract_directly(self):
        ka = _make_kernel_agent_stub()
        with pytest.raises(TypeError):
            SKLogicBase(kernel_agent=ka)
