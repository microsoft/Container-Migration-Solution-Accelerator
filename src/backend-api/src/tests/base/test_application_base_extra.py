"""Additional tests for Application_Base class to improve coverage."""
import os
import logging
from unittest.mock import Mock, patch, MagicMock
import pytest
import tempfile

from libs.base.application_base import Application_Base
from libs.application.application_context import AppContext


class ConcreteApplication(Application_Base):
    """Concrete implementation for testing."""

    def run(self):
        return "run_result"

    def initialize(self):
        return "initialize_result"


def test_application_base_with_env_file():
    """Test Application_Base with a provided .env file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = os.path.join(tmpdir, ".env")
        with open(env_file, "w") as f:
            f.write("TEST_VAR=test_value\n")

        app = ConcreteApplication(env_file_path=env_file)

        assert app.application_context is not None
        assert app.application_context.configuration is not None


def test_application_base_initialization_calls_initialize():
    """Test that __init__ calls the initialize method."""

    class TrackingApplication(Application_Base):
        def __init__(self, **kwargs):
            self.initialize_called = False
            super().__init__(**kwargs)

        def run(self):
            pass

        def initialize(self):
            self.initialize_called = True

    app = TrackingApplication(env_file_path=None)
    assert app.initialize_called is True


def test_application_base_sets_default_azure_credential():
    """Test that Application_Base sets DefaultAzureCredential."""
    app = ConcreteApplication(env_file_path=None)

    assert app.application_context.credential is not None


def test_application_base_logging_disabled_by_default():
    """Test that logging is disabled by default."""
    app = ConcreteApplication(env_file_path=None)

    # Default logging should be disabled
    assert app.application_context.configuration.app_logging_enable is False


def test_application_base_logging_enabled():
    """Test Application_Base with logging enabled."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = os.path.join(tmpdir, ".env")
        with open(env_file, "w") as f:
            f.write("APP_LOGGING_ENABLE=true\n")
            f.write("APP_LOGGING_LEVEL=DEBUG\n")

        with patch.dict(os.environ, {"APP_LOGGING_ENABLE": "true"}):
            app = ConcreteApplication(env_file_path=env_file)
            assert app.application_context is not None


def test_application_base_load_env_with_none_path():
    """Test _load_env with None path."""
    app = ConcreteApplication(env_file_path=None)

    # Should call _get_derived_class_location if env_file_path is None
    result = app._load_env(env_file_path=None)

    # Should return a path to .env
    assert isinstance(result, str)
    assert ".env" in result


def test_application_base_load_env_returns_path():
    """Test that _load_env returns the path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = os.path.join(tmpdir, ".env")
        with open(env_file, "w") as f:
            f.write("TEST=value\n")

        result = ConcreteApplication(env_file_path=None)._load_env(env_file_path=env_file)

        assert result == env_file


def test_application_base_load_env_creates_app_context():
    """Test that application context is created even if .env is missing."""
    app = ConcreteApplication(env_file_path=None)

    # Even if .env doesn't exist, app context should be created
    assert app.application_context is not None
    assert isinstance(app.application_context, AppContext)


def test_application_base_run_method():
    """Test that run method can be called."""
    app = ConcreteApplication(env_file_path=None)

    result = app.run()
    assert result == "run_result"


def test_application_base_initialize_method():
    """Test that initialize method can be called."""
    app = ConcreteApplication(env_file_path=None)

    result = app.initialize()
    assert result == "initialize_result"


def test_application_base_get_derived_class_location_returns_string():
    """Test that _get_derived_class_location returns a string path."""
    app = ConcreteApplication(env_file_path=None)

    location = app._get_derived_class_location()

    assert isinstance(location, str)
    assert len(location) > 0
    assert os.path.exists(os.path.dirname(location))


def test_application_base_app_context_not_none():
    """Test that application_context is always set."""
    app = ConcreteApplication(env_file_path=None)

    assert app.application_context is not None
    assert isinstance(app.application_context, AppContext)


def test_application_base_configuration_not_none():
    """Test that configuration is set in app context."""
    app = ConcreteApplication(env_file_path=None)

    assert app.application_context.configuration is not None


def test_application_base_abstract_methods():
    """Test that run and initialize must be implemented."""

    with pytest.raises(TypeError):
        # Cannot instantiate Application_Base with unimplemented abstract methods
        Application_Base(env_file_path=None)


def test_application_base_azure_logging_packages_not_set():
    """Test with no azure logging packages configured."""
    app = ConcreteApplication(env_file_path=None)

    # Azure logging packages should be None or empty by default
    assert (
        app.application_context.configuration.azure_logging_packages is None
        or app.application_context.configuration.azure_logging_packages == ""
    )


def test_application_base_with_azure_logging():
    """Test Application_Base with Azure logging packages configured."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = os.path.join(tmpdir, ".env")
        with open(env_file, "w") as f:
            f.write("APP_LOGGING_ENABLE=true\n")
            f.write("AZURE_LOGGING_PACKAGES=azure.core,azure.identity\n")

        with patch.dict(
            os.environ,
            {
                "APP_LOGGING_ENABLE": "true",
                "AZURE_LOGGING_PACKAGES": "azure.core,azure.identity",
            },
        ):
            app = ConcreteApplication(env_file_path=env_file)
            assert app.application_context is not None
