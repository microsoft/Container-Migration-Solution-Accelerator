"""Tests for application.Application bootstrap."""

from application import Application
from libs.base.typed_fastapi import TypedFastAPI
from libs.services.interfaces import IDataService, IHttpService, ILoggerService
from libs.services.process_services import ProcessService


def test_application_initializes_typed_fastapi():
    app = Application()
    assert isinstance(app.app, TypedFastAPI)
    assert app.app.title == "FastAPI Application"
    assert app.app.version == "1.0.0"


def test_application_sets_app_context_on_app():
    app = Application()
    assert app.app.app_context is app.application_context


def test_application_registers_core_services():
    app = Application()
    ctx = app.application_context
    assert ctx.get_service(ILoggerService) is not None
    assert ctx.get_service(IHttpService) is not None
    assert ctx.get_service(IDataService) is not None
    assert ctx.get_service(ProcessService) is not None


def test_application_includes_routers():
    app = Application()
    paths = {route.path for route in app.app.routes}
    # router_files
    assert "/api/file/upload" in paths
    # router_process
    assert "/api/process/create" in paths
    # http_probes
    assert "/health" in paths
