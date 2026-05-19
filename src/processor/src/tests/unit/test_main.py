# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Coverage for src/main.py — the direct-execution entry point.

Tests instantiate Application via __new__ to avoid loading .env / Azure
credentials, and verify register_services() and run() wiring.
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch


def _run(coro):
    return asyncio.run(coro)


def _make_app():
    """Build Application without invoking ApplicationBase.__init__."""
    import main as main_mod
    app = main_mod.Application.__new__(main_mod.Application)
    app.application_context = MagicMock()
    app.application_context.llm_settings = MagicMock()
    return app


class TestApplicationInitializeAndRegister:
    def test_initialize_logs_and_registers(self, caplog):
        import main as main_mod
        app = _make_app()
        # Make the chain returned by add_singleton fluent
        chain = MagicMock()
        chain.add_singleton.return_value = chain
        chain.add_async_singleton.return_value = chain
        chain.add_transient.return_value = chain
        # Pretend the framework helper service exists
        helper = MagicMock()
        app.application_context.add_singleton.return_value = chain
        app.application_context.get_service.return_value = helper

        with caplog.at_level(logging.INFO):
            app.initialize()
        # register_services was called via initialize()
        assert app.application_context.add_singleton.call_count >= 1
        helper.initialize.assert_called_once()

    def test_register_services_handles_cosmos_import_error(self):
        app = _make_app()
        chain = MagicMock()
        chain.add_singleton.return_value = chain
        chain.add_async_singleton.return_value = chain
        chain.add_transient.return_value = chain
        helper = MagicMock()
        app.application_context.add_singleton.return_value = chain
        app.application_context.get_service.return_value = helper

        # Simulate cosmos checkpoint module failing to import
        with patch.dict(
            "sys.modules",
            {"libs.agent_framework.cosmos_checkpoint_storage": None},
        ):
            app.register_services()
        # Should not raise — the except path is exercised


class TestApplicationRun:
    def test_run_calls_migration_processor(self):
        app = _make_app()
        proc = MagicMock()
        proc.run = AsyncMock()
        app.application_context.get_service.return_value = proc
        _run(app.run())
        proc.run.assert_awaited_once()


class TestMainCoroutine:
    def test_main_constructs_initializes_runs(self):
        import main as main_mod
        with patch.object(main_mod, "Application") as MockApp:
            instance = MockApp.return_value
            instance.run = AsyncMock()
            instance.initialize = MagicMock()
            _run(main_mod.main())
            instance.initialize.assert_called_once()
            instance.run.assert_awaited_once()
