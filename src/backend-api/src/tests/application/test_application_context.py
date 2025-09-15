from azure.identity import DefaultAzureCredential

from libs.application.application_configuration import Configuration
from libs.application.application_context import AppContext


def test_application_context():
    app_context = AppContext()
    assert app_context is not None


def test_application_context_configuration():
    app_context = AppContext()
    app_context.set_configuration(Configuration())
    assert app_context.configuration is not None
    assert (
        app_context.configuration.app_sample_variable
        == "Application Template Sample Variable from App Configuration Store"
    )  # "Hello World!"


def test_application_context_credential():
    app_context = AppContext()
    app_context.set_credential(DefaultAzureCredential())
    assert app_context.credential is not None
