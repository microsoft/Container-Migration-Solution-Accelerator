"""Tests for main.get_app() factory."""

import importlib
from unittest.mock import MagicMock, patch


def test_get_app_returns_app_and_caches_singleton():
    """get_app should call Application() once and reuse the cached instance."""
    fake_app = MagicMock(name="FastAPIApp")
    fake_application = MagicMock()
    fake_application.app = fake_app

    # Reset module-level singleton, then patch Application before reload
    import main as main_module

    main_module._app_instance = None
    with patch("main.Application", return_value=fake_application) as MockApp:
        first = main_module.get_app()
        second = main_module.get_app()
        assert first is fake_app
        assert second is fake_app
        assert MockApp.call_count == 1
