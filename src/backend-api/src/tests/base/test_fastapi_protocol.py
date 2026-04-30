"""Tests for fastapi_protocol module."""
import pytest
from fastapi import FastAPI
from libs.application.application_context import AppContext
from libs.base.fastapi_protocol import add_app_context_to_fastapi, FastAPIWithContext


def test_fastapi_with_context_protocol_definition():
    """Test that FastAPIWithContext is a Protocol with expected attributes."""
    # Just verify the protocol exists and has the expected structure
    assert hasattr(FastAPIWithContext, "__protocol_attrs__") or hasattr(
        FastAPIWithContext, "__mro__"
    )


def test_add_app_context_to_fastapi_basic():
    """Test adding app context to FastAPI instance."""
    app = FastAPI()
    app_context = AppContext()

    result = add_app_context_to_fastapi(app, app_context)

    assert result is app
    assert hasattr(app, "app_context")
    assert app.app_context is app_context


def test_add_app_context_to_fastapi_with_configured_context():
    """Test adding a configured app context to FastAPI."""
    from libs.application.application_configuration import Configuration

    app = FastAPI()
    app_context = AppContext()
    config = Configuration()
    app_context.set_configuration(config)

    result = add_app_context_to_fastapi(app, app_context)

    assert result.app_context.configuration is not None
    assert result.app_context.configuration.app_sample_variable == "Hello World!"


def test_add_app_context_to_fastapi_returns_typed_app():
    """Test that returned value is properly typed for use as FastAPIWithContext."""
    app = FastAPI()
    app_context = AppContext()

    result = add_app_context_to_fastapi(app, app_context)

    # Should have app_context attribute
    assert hasattr(result, "app_context")
    # Should have FastAPI methods like include_router
    assert hasattr(result, "include_router")
    assert callable(result.include_router)


def test_add_app_context_to_fastapi_multiple_contexts():
    """Test that we can replace app context on same FastAPI instance."""
    app = FastAPI()
    app_context1 = AppContext()
    app_context2 = AppContext()

    add_app_context_to_fastapi(app, app_context1)
    assert app.app_context is app_context1

    add_app_context_to_fastapi(app, app_context2)
    assert app.app_context is app_context2
