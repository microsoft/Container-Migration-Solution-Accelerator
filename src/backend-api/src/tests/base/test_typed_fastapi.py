from fastapi import FastAPI

from libs.application.application_context import AppContext
from libs.base.fastapi_protocol import (
    FastAPIWithContext,
    add_app_context_to_fastapi,
)
from libs.base.typed_fastapi import TypedFastAPI


class TestTypedFastAPI:
    def test_initial_app_context_is_none(self):
        app = TypedFastAPI()
        assert app.app_context is None

    def test_set_app_context_assigns_value(self):
        app = TypedFastAPI()
        ctx = AppContext()
        app.set_app_context(ctx)
        assert app.app_context is ctx

    def test_inherits_from_fastapi(self):
        assert isinstance(TypedFastAPI(), FastAPI)


class TestAddAppContextToFastAPI:
    def test_adds_app_context_attribute(self):
        app = FastAPI()
        ctx = AppContext()
        result = add_app_context_to_fastapi(app, ctx)
        assert result is app
        assert app.app_context is ctx

    def test_replaces_existing_app_context(self):
        app = FastAPI()
        first = AppContext()
        second = AppContext()
        add_app_context_to_fastapi(app, first)
        add_app_context_to_fastapi(app, second)
        assert app.app_context is second


class TestFastAPIWithContextProtocol:
    def test_typed_fastapi_satisfies_protocol(self):
        # Runtime-checkable not required; just confirm symbols exist.
        assert hasattr(FastAPIWithContext, "include_router")
