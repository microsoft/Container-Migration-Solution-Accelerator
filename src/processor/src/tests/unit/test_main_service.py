# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main_service import QueueMigrationServiceApp


def _run(coro):
    return asyncio.run(coro)


def _make_app(queue_service=None, control_api=None, debug=False, ctx=None):
    """Build QueueMigrationServiceApp via __new__ — avoids ApplicationBase init."""
    app = QueueMigrationServiceApp.__new__(QueueMigrationServiceApp)
    app.queue_service = queue_service
    app.control_api = control_api
    app.config_override = {}
    app.debug_mode = debug
    app.application_context = ctx or MagicMock()
    app.app_context = app.application_context
    return app


class TestServiceStatus:
    def test_is_service_running_false_without_queue(self):
        app = _make_app(queue_service=None)
        assert app.is_service_running() is False

    def test_is_service_running_uses_queue_state(self):
        q = MagicMock()
        q.is_running = True
        app = _make_app(queue_service=q)
        assert app.is_service_running() is True

    @patch("main_service.asyncio")
    def test_get_service_status_not_initialized(self, mock_asyncio):
        mock_loop = MagicMock()
        mock_loop.time.return_value = 1000.0
        mock_asyncio.get_event_loop.return_value = mock_loop
        app = _make_app(queue_service=None)
        status = app.get_service_status()
        assert status["status"] == "not_initialized"
        assert status["running"] is False
        assert status["docker_health"] == "unhealthy"

    def test_get_service_status_when_running(self):
        q = MagicMock()
        q.is_running = True
        q.get_service_status.return_value = {"status": "running"}
        app = _make_app(queue_service=q)
        status = app.get_service_status()
        assert status["docker_health"] == "healthy"
        assert status["running"] is True


class TestBuildServiceConfig:
    def test_uses_env_var_defaults(self, monkeypatch):
        for k in [
            "VISIBILITY_TIMEOUT_MINUTES",
            "POLL_INTERVAL_SECONDS",
            "MESSAGE_TIMEOUT_MINUTES",
            "CONCURRENT_WORKERS",
        ]:
            monkeypatch.delenv(k, raising=False)
        ctx = MagicMock()
        ctx.configuration.storage_queue_account = "acct"
        ctx.configuration.storage_account_process_queue = "queue"
        app = _make_app(ctx=ctx)
        cfg = app._build_service_config()
        assert cfg.storage_account_name == "acct"
        assert cfg.queue_name == "queue"
        assert cfg.visibility_timeout_minutes == 5
        assert cfg.concurrent_workers == 1

    def test_applies_override(self, monkeypatch):
        ctx = MagicMock()
        ctx.configuration.storage_queue_account = "acct"
        ctx.configuration.storage_account_process_queue = "queue"
        app = _make_app(ctx=ctx)
        cfg = app._build_service_config({"concurrent_workers": 7, "ignored_field": "x"})
        assert cfg.concurrent_workers == 7

    def test_uses_env_var_overrides(self, monkeypatch):
        monkeypatch.setenv("VISIBILITY_TIMEOUT_MINUTES", "12")
        monkeypatch.setenv("POLL_INTERVAL_SECONDS", "3")
        monkeypatch.setenv("MESSAGE_TIMEOUT_MINUTES", "30")
        monkeypatch.setenv("CONCURRENT_WORKERS", "4")
        ctx = MagicMock()
        ctx.configuration.storage_queue_account = "acct"
        ctx.configuration.storage_account_process_queue = "queue"
        app = _make_app(ctx=ctx, debug=True)
        cfg = app._build_service_config()
        assert cfg.visibility_timeout_minutes == 12
        assert cfg.poll_interval_seconds == 3
        assert cfg.message_timeout_minutes == 30
        assert cfg.concurrent_workers == 4


class TestBuildControlApi:
    def test_disabled_by_env(self, monkeypatch):
        monkeypatch.setenv("CONTROL_API_ENABLED", "0")
        app = _make_app()
        result = _run(app._build_control_api())
        assert result is None

    def test_builds_with_env_settings(self, monkeypatch):
        monkeypatch.setenv("CONTROL_API_ENABLED", "1")
        monkeypatch.setenv("CONTROL_API_TOKEN", "token-x")
        monkeypatch.setenv("CONTROL_API_HOST", "127.0.0.1")
        monkeypatch.setenv("CONTROL_API_PORT", "9090")
        ctx = MagicMock()
        ctx.get_service_async = AsyncMock(return_value=MagicMock())
        app = _make_app(ctx=ctx)
        with patch("main_service.ControlApiServer") as srv_cls:
            srv_cls.return_value = "server"
            result = _run(app._build_control_api())
        assert result == "server"

    def test_invalid_port_falls_back(self, monkeypatch):
        monkeypatch.setenv("CONTROL_API_ENABLED", "1")
        monkeypatch.setenv("CONTROL_API_PORT", "not-a-number")
        ctx = MagicMock()
        ctx.get_service_async = AsyncMock(return_value=MagicMock())
        app = _make_app(ctx=ctx)
        with patch("main_service.ControlApiServer") as srv_cls, patch(
            "main_service.ControlApiConfig"
        ) as cfg_cls:
            srv_cls.return_value = "s"
            _run(app._build_control_api())
        kwargs = cfg_cls.call_args.kwargs
        assert kwargs["port"] == 8080

    def test_falls_back_to_new_control_manager_on_di_error(self, monkeypatch):
        monkeypatch.setenv("CONTROL_API_ENABLED", "1")
        ctx = MagicMock()
        ctx.get_service_async = AsyncMock(side_effect=RuntimeError("not registered"))
        app = _make_app(ctx=ctx)
        with patch("main_service.ProcessControlManager") as pcm_cls, patch(
            "main_service.ControlApiServer"
        ) as srv_cls:
            srv_cls.return_value = "s"
            _run(app._build_control_api())
        pcm_cls.assert_called_once_with(app.application_context)


class TestStartShutdown:
    def test_start_service_raises_without_init(self):
        app = _make_app(queue_service=None)
        with pytest.raises(RuntimeError, match="not initialized"):
            _run(app.start_service())

    def test_start_service_runs_and_shuts_down(self):
        q = MagicMock()
        q.start_service = AsyncMock()
        q.stop_service = AsyncMock()
        q.is_running = True
        app = _make_app(queue_service=q)
        # Avoid building control API
        app._build_control_api = AsyncMock(return_value=None)
        _run(app.start_service())
        q.start_service.assert_awaited_once()

    def test_start_service_with_control_api_enabled(self):
        q = MagicMock()
        q.start_service = AsyncMock()
        q.stop_service = AsyncMock()
        api = MagicMock()
        api.start = AsyncMock()
        api.stop = AsyncMock()
        app = _make_app(queue_service=q)
        app._build_control_api = AsyncMock(return_value=api)
        _run(app.start_service())
        api.start.assert_awaited_once()
        api.stop.assert_awaited_once()

    def test_start_service_handles_keyboard_interrupt(self):
        q = MagicMock()
        q.start_service = AsyncMock(side_effect=KeyboardInterrupt())
        q.stop_service = AsyncMock()
        app = _make_app(queue_service=q)
        app._build_control_api = AsyncMock(return_value=None)
        _run(app.start_service())  # swallowed, no raise

    def test_start_service_handles_generic_exception(self):
        q = MagicMock()
        q.start_service = AsyncMock(side_effect=RuntimeError("boom"))
        q.stop_service = AsyncMock()
        app = _make_app(queue_service=q)
        app._build_control_api = AsyncMock(return_value=None)
        _run(app.start_service())  # swallowed, no raise

    def test_start_service_handles_build_control_api_exception(self):
        q = MagicMock()
        q.start_service = AsyncMock()
        q.stop_service = AsyncMock()
        app = _make_app(queue_service=q)
        app._build_control_api = AsyncMock(side_effect=RuntimeError("nope"))
        _run(app.start_service())  # warned + control_api stays None

    def test_shutdown_service_clears_state(self):
        q = MagicMock()
        q.stop_service = AsyncMock()
        api = MagicMock()
        api.stop = AsyncMock()
        app = _make_app(queue_service=q, control_api=api)
        _run(app.shutdown_service())
        assert app.queue_service is None
        assert app.control_api is None

    def test_force_stop_service(self):
        q = MagicMock()
        q.force_stop = AsyncMock()
        app = _make_app(queue_service=q)
        _run(app.force_stop_service())
        assert app.queue_service is None

    def test_force_stop_no_queue(self):
        app = _make_app(queue_service=None)
        _run(app.force_stop_service())  # no-op


class TestRunEntrypoint:
    def test_run_calls_start_service(self):
        app = _make_app()
        app.start_service = AsyncMock()
        _run(app.run())
        app.start_service.assert_awaited_once()


class TestRunQueueService:
    def test_run_queue_service_runs_app(self):
        from main_service import run_queue_service

        with patch("main_service.QueueMigrationServiceApp") as app_cls:
            instance = MagicMock()
            instance.run = AsyncMock()
            instance.queue_service = MagicMock()
            instance.queue_service.stop_service = AsyncMock()
            app_cls.return_value = instance
            _run(run_queue_service(debug_mode=True))
        instance.run.assert_awaited_once()

    def test_run_queue_service_handles_keyboard_interrupt(self):
        from main_service import run_queue_service

        with patch("main_service.QueueMigrationServiceApp") as app_cls:
            instance = MagicMock()
            instance.run = AsyncMock(side_effect=KeyboardInterrupt())
            instance.queue_service = MagicMock()
            instance.queue_service.stop_service = AsyncMock()
            app_cls.return_value = instance
            _run(run_queue_service())  # no raise

    def test_run_queue_service_reraises_other_exceptions(self):
        from main_service import run_queue_service

        with patch("main_service.QueueMigrationServiceApp") as app_cls:
            instance = MagicMock()
            instance.run = AsyncMock(side_effect=ValueError("oops"))
            instance.queue_service = MagicMock()
            instance.queue_service.stop_service = AsyncMock()
            app_cls.return_value = instance
            with pytest.raises(ValueError):
                _run(run_queue_service())
