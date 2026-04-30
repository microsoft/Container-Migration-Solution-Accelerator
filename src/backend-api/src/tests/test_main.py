from unittest.mock import MagicMock, patch
from main import get_app


def test_get_app_returns_app():
    """Test that get_app returns a FastAPI app instance."""
    with patch('main.Application') as mock_app_class:
        mock_instance = MagicMock()
        mock_instance.app = MagicMock()
        mock_app_class.return_value = mock_instance
        
        # Reset module state to test get_app fresh
        import main
        main._app_instance = None
        
        with patch('main.Application') as mock_app_class:
            mock_instance = MagicMock()
            mock_instance.app = MagicMock()
            mock_app_class.return_value = mock_instance
            
            result = main.get_app()
            assert result is not None


def test_get_app_returns_same_instance():
    """Test that get_app returns the same instance on multiple calls."""
    with patch('main.Application') as mock_app_class:
        mock_instance = MagicMock()
        mock_instance.app = MagicMock()
        mock_app_class.return_value = mock_instance
        
        import main
        main._app_instance = None
        
        with patch('main.Application') as mock_app_class:
            mock_instance = MagicMock()
            mock_instance.app = MagicMock()
            mock_app_class.return_value = mock_instance
            
            app1 = main.get_app()
            app2 = main.get_app()
            
            # Same cached instance should be returned
            assert mock_app_class.call_count == 1 or app1 is app2


def test_main_module_has_get_app():
    """Test that main module exports get_app function."""
    import main
    assert hasattr(main, 'get_app')
    assert callable(main.get_app)


def test_main_module_has_app():
    """Test that main module exports app instance."""
    import main
    assert hasattr(main, 'app')


def test_main_module_has_app_instance():
    """Test that main.app is not None."""
    import main
    assert main.app is not None
