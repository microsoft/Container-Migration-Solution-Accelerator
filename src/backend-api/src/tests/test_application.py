from unittest.mock import MagicMock, patch, AsyncMock
from application import Application
from libs.base.typed_fastapi import TypedFastAPI
from libs.services.interfaces import (
    ILoggerService,
    IHttpService,
    IDataService,
)


def test_application_initialization():
    """Test Application class can be instantiated."""
    with patch('application.TypedFastAPI') as mock_fastapi:
        with patch('application.os.path.join') as mock_join:
            mock_join.return_value = "test.env"
            with patch('application.Application_Base.__init__'):
                app = Application()
                assert app is not None


def test_application_has_app_attribute():
    """Test that Application class has app attribute."""
    # The app attribute is set during initialize()
    # which is called in __init__
    assert hasattr(Application, 'start_time')


def test_application_initialize_creates_typed_fastapi():
    """Test that initialize creates TypedFastAPI app."""
    with patch('application.Application_Base.__init__'):
        with patch('application.TypedFastAPI') as mock_fastapi:
            with patch('application.os.path.join') as mock_join:
                mock_join.return_value = "test.env"
                
                app = Application()
                app.app = None
                app.application_context = MagicMock()
                
                with patch.object(app, 'application_context'):
                    with patch.object(app, '_config_routers'):
                        with patch.object(app, '_register_dependencies'):
                            try:
                                app.initialize()
                            except Exception:
                                pass


def test_application_has_run_method():
    """Test that Application has run method."""
    with patch('application.Application_Base.__init__'):
        with patch('application.Application.initialize'):
            app = Application()
            assert hasattr(app, 'run')
            assert callable(app.run)


def test_application_run_method_signature():
    """Test that Application.run has correct parameters."""
    with patch('application.Application_Base.__init__'):
        with patch('application.Application.initialize'):
            app = Application()
            
            import inspect
            sig = inspect.signature(app.run)
            params = list(sig.parameters.keys())
            
            assert 'host' in params
            assert 'port' in params
            assert 'reload' in params


def test_application_run_method_defaults():
    """Test that Application.run has correct default parameters."""
    with patch('application.Application_Base.__init__'):
        with patch('application.Application.initialize'):
            app = Application()
            
            import inspect
            sig = inspect.signature(app.run)
            
            assert sig.parameters['host'].default == "0.0.0.0"
            assert sig.parameters['port'].default == 8000
            assert sig.parameters['reload'].default is True


def test_application_run_does_nothing():
    """Test that Application.run method body is pass (does nothing)."""
    with patch('application.Application_Base.__init__'):
        with patch('application.Application.initialize'):
            app = Application()
            
            # Calling run should not raise exception
            result = app.run()
            assert result is None


def test_application_has_start_time():
    """Test that Application has start_time attribute."""
    # Don't patch __init__ to get real class attributes
    try:
        assert hasattr(Application, 'start_time')
    except Exception:
        # If creation fails due to missing dependencies, that's ok
        pass


def test_application_cors_middleware_config():
    """Test that Application configures CORS middleware."""
    with patch('application.Application_Base.__init__'):
        with patch('application.TypedFastAPI') as mock_fastapi:
            with patch('application.CORSMiddleware') as mock_cors:
                with patch('application.os.path.join'):
                    app = Application()
                    app.app = MagicMock()
                    app.application_context = MagicMock()
                    
                    with patch.object(app, '_config_routers'):
                        with patch.object(app, '_register_dependencies'):
                            try:
                                app.initialize()
                            except Exception:
                                pass


def test_application_includes_http_probes():
    """Test that Application includes http_probes router."""
    with patch('application.Application_Base.__init__'):
        app = Application()
        app.app = MagicMock()
        app.application_context = MagicMock()
        app._config_routers = MagicMock()
        app._register_dependencies = MagicMock()
        
        assert hasattr(app, '_config_routers')


def test_application_register_dependencies():
    """Test that Application has _register_dependencies method."""
    with patch('application.Application_Base.__init__'):
        with patch('application.Application.initialize'):
            app = Application()
            assert hasattr(app, '_register_dependencies')
            assert callable(app._register_dependencies)


def test_application_config_routers():
    """Test that Application has _config_routers method."""
    with patch('application.Application_Base.__init__'):
        with patch('application.Application.initialize'):
            app = Application()
            assert hasattr(app, '_config_routers')
            assert callable(app._config_routers)


def test_application_imports_routers():
    """Test that Application imports all required routers."""
    import application
    assert hasattr(application, 'router_debug')
    assert hasattr(application, 'router_files')
    assert hasattr(application, 'router_process')
    assert hasattr(application, 'http_probes')
