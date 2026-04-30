"""Tests for TypedFastAPI class."""
import pytest
from fastapi import FastAPI
from libs.application.application_context import AppContext
from libs.base.typed_fastapi import TypedFastAPI


def test_typed_fastapi_inherits_from_fastapi():
    """Test that TypedFastAPI is a subclass of FastAPI."""
    app = TypedFastAPI()
    assert isinstance(app, FastAPI)


def test_typed_fastapi_initialization():
    """Test TypedFastAPI initialization."""
    app = TypedFastAPI()
    assert app.app_context is None


def test_typed_fastapi_with_kwargs():
    """Test TypedFastAPI initialization with FastAPI kwargs."""
    app = TypedFastAPI(title="Test API", version="1.0.0")
    assert app.title == "Test API"
    assert app.version == "1.0.0"
    assert app.app_context is None


def test_set_app_context():
    """Test setting app context on TypedFastAPI."""
    app = TypedFastAPI()
    app_context = AppContext()

    app.set_app_context(app_context)

    assert app.app_context is app_context


def test_set_app_context_with_configuration():
    """Test setting a configured app context."""
    from libs.application.application_configuration import Configuration

    app = TypedFastAPI()
    app_context = AppContext()
    config = Configuration()
    app_context.set_configuration(config)

    app.set_app_context(app_context)

    assert app.app_context.configuration is not None
    assert app.app_context.configuration.app_sample_variable == "Hello World!"


def test_typed_fastapi_app_context_attribute_type():
    """Test that app_context attribute has proper type."""
    app = TypedFastAPI()
    app_context = AppContext()

    app.set_app_context(app_context)

    assert isinstance(app.app_context, AppContext)


def test_typed_fastapi_set_app_context_returns_none():
    """Test that set_app_context returns None (void method)."""
    app = TypedFastAPI()
    app_context = AppContext()

    result = app.set_app_context(app_context)

    assert result is None


def test_typed_fastapi_multiple_context_changes():
    """Test changing app context multiple times."""
    app = TypedFastAPI()
    app_context1 = AppContext()
    app_context2 = AppContext()

    app.set_app_context(app_context1)
    assert app.app_context is app_context1

    app.set_app_context(app_context2)
    assert app.app_context is app_context2


def test_typed_fastapi_with_standard_fastapi_features():
    """Test that TypedFastAPI maintains FastAPI functionality."""
    app = TypedFastAPI()
    app_context = AppContext()
    app.set_app_context(app_context)

    # Should still be able to use FastAPI decorators
    @app.get("/")
    def read_root():
        return {"message": "Hello"}

    # Check the route was added
    assert len(app.routes) > 0
