# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Additional unit tests for `services.process_control` and `services.control_api`."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web

from services import control_api as ca
from services import process_control as pc


def _run(coro):
    return asyncio.run(coro)


# ============== ProcessControlManager additional branches ==============


def _make_app_context_with_cosmos(url: str, container: str = "ctrl"):
    cfg = SimpleNamespace(
        cosmos_db_account_url=url,
        cosmos_db_database_name="db",
        cosmos_db_control_container_name=container,
    )
    return SimpleNamespace(configuration=cfg)


def test_process_control_manager_dev_mode_when_no_cosmos_url():
    ctx = _make_app_context_with_cosmos("")
    mgr = pc.ProcessControlManager(app_context=ctx)
    assert mgr.repository is None


def test_process_control_manager_dev_mode_when_localhost():
    ctx = _make_app_context_with_cosmos("https://localhost:8081")
    mgr = pc.ProcessControlManager(app_context=ctx)
    assert mgr.repository is None


def test_process_control_manager_dev_mode_when_placeholder_url():
    ctx = _make_app_context_with_cosmos("http://<your-cosmos-url>")
    mgr = pc.ProcessControlManager(app_context=ctx)
    assert mgr.repository is None


def test_process_control_manager_dev_mode_when_placeholder_container():
    ctx = _make_app_context_with_cosmos("https://prod.documents.azure.com", "<placeholder>")
    mgr = pc.ProcessControlManager(app_context=ctx)
    assert mgr.repository is None


def test_process_control_manager_creates_repository_for_real_cosmos():
    ctx = _make_app_context_with_cosmos(
        "https://prod.documents.azure.com:443/", "ctrl"
    )
    fake_repo = MagicMock()
    with patch.object(pc, "ProcessControlRepository", return_value=fake_repo) as ctor:
        mgr = pc.ProcessControlManager(app_context=ctx)
    ctor.assert_called_once_with(ctx)
    assert mgr.repository is fake_repo


def test_process_control_repository_init_raises_without_config():
    ctx = SimpleNamespace(configuration=None)
    with pytest.raises(ValueError):
        pc.ProcessControlRepository(ctx)


def test_process_control_repository_init_calls_super():
    ctx = _make_app_context_with_cosmos(
        "https://prod.documents.azure.com", "ctrl-container"
    )
    captured = {}

    def _fake_super_init(self, **kw):
        captured.update(kw)

    with patch.object(pc.RepositoryBase, "__init__", _fake_super_init):
        pc.ProcessControlRepository(ctx)
    assert captured["account_url"] == "https://prod.documents.azure.com"
    assert captured["database_name"] == "db"
    assert captured["container_name"] == "ctrl-container"


def test_get_returns_none_for_empty_process_id():
    mgr = pc.ProcessControlManager(app_context=None)
    assert _run(mgr.get("")) is None


def test_get_uses_repository_when_present():
    mgr = pc.ProcessControlManager(app_context=None)
    fake_repo = MagicMock()
    fake_repo.get_async = AsyncMock(return_value="record")
    mgr.repository = fake_repo
    result = _run(mgr.get("p1"))
    assert result == "record"
    fake_repo.get_async.assert_awaited_once_with("p1")


def test_get_returns_none_when_repository_raises():
    mgr = pc.ProcessControlManager(app_context=None)
    fake_repo = MagicMock()
    fake_repo.get_async = AsyncMock(side_effect=Exception("cosmos down"))
    mgr.repository = fake_repo
    assert _run(mgr.get("p1")) is None


def test_ack_executing_returns_silently_when_no_kill_requested():
    mgr = pc.ProcessControlManager(app_context=None)
    # Pre-store a record without kill_requested
    record = pc.ProcessControl(id="p1")
    mgr._in_memory["p1"] = record
    _run(mgr.ack_executing("p1", instance_id="inst"))
    # State should remain unchanged because kill_requested is False
    assert record.kill_state == ""
    assert record.kill_ack_instance_id == ""


def test_ack_executing_creates_record_if_missing_then_returns_when_no_kill_requested():
    mgr = pc.ProcessControlManager(app_context=None)
    _run(mgr.ack_executing("ghost", instance_id="inst"))
    # Because the new record doesn't have kill_requested=True it must NOT be upserted
    assert "ghost" not in mgr._in_memory


def test_mark_executed_creates_record_if_missing():
    mgr = pc.ProcessControlManager(app_context=None)
    _run(mgr.mark_executed("new", instance_id="inst"))
    rec = _run(mgr.get("new"))
    assert rec is not None
    assert rec.kill_state == "executed"
    assert rec.kill_ack_instance_id == "inst"
    assert rec.kill_executed_at


def test_mark_executed_preserves_existing_ack_instance_id():
    mgr = pc.ProcessControlManager(app_context=None)
    _run(mgr.request_kill("p1"))
    _run(mgr.ack_executing("p1", instance_id="orig"))
    _run(mgr.mark_executed("p1", instance_id="new"))
    rec = _run(mgr.get("p1"))
    assert rec.kill_ack_instance_id == "orig"


def test_upsert_via_repository_update_when_existing():
    mgr = pc.ProcessControlManager(app_context=None)
    fake_repo = MagicMock()
    fake_repo.get_async = AsyncMock(return_value="exists")
    fake_repo.update_async = AsyncMock()
    fake_repo.add_async = AsyncMock()
    mgr.repository = fake_repo
    record = pc.ProcessControl(id="p1")
    _run(mgr._upsert(record))
    fake_repo.update_async.assert_awaited_once_with(record)
    fake_repo.add_async.assert_not_awaited()


def test_upsert_via_repository_add_when_not_existing():
    mgr = pc.ProcessControlManager(app_context=None)
    fake_repo = MagicMock()
    fake_repo.get_async = AsyncMock(return_value=None)
    fake_repo.update_async = AsyncMock()
    fake_repo.add_async = AsyncMock()
    mgr.repository = fake_repo
    record = pc.ProcessControl(id="p1")
    _run(mgr._upsert(record))
    fake_repo.add_async.assert_awaited_once_with(record)
    fake_repo.update_async.assert_not_awaited()


def test_upsert_swallows_repository_exception():
    mgr = pc.ProcessControlManager(app_context=None)
    fake_repo = MagicMock()
    fake_repo.get_async = AsyncMock(side_effect=Exception("fail"))
    mgr.repository = fake_repo
    record = pc.ProcessControl(id="p1")
    # Should not raise
    _run(mgr._upsert(record))


def test_utc_timestamp_format():
    ts = pc._utc_timestamp()
    assert ts.endswith("UTC")
    assert len(ts) >= len("YYYY-MM-DD HH:MM:SS UTC")


# ============== Control API edge-case branches ==============


def _build_request(method="GET", path="/", match_info=None, headers=None,
                   can_read_body=False, json_value=None, json_raises=False):
    """Build a minimal mock aiohttp Request."""
    req = MagicMock()
    req.method = method
    req.path = path
    req.match_info = match_info or {}
    req.headers = headers or {}
    req.can_read_body = can_read_body
    if json_raises:
        req.json = AsyncMock(side_effect=Exception("bad json"))
    else:
        req.json = AsyncMock(return_value=json_value)
    return req


def _extract_handler(app, method, path):
    """Extract the underlying async handler function for a (method, path) route."""
    for route in app.router.routes():
        if route.method == method:
            info = route.get_info()
            if info.get("path") == path or info.get("formatter") == path:
                return route.handler
    raise AssertionError(f"No route for {method} {path}")


def test_create_control_app_health_endpoint():
    mgr = pc.ProcessControlManager(app_context=None)
    app = ca.create_control_app(mgr)
    health_handler = _extract_handler(app, "GET", "/health")
    req = _build_request(method="GET", path="/health")
    resp = _run(health_handler(req))
    assert resp.status == 200
    assert b'"status"' in resp.body
    assert b'"ok"' in resp.body


def test_get_control_missing_process_id_returns_400():
    mgr = pc.ProcessControlManager(app_context=None)
    app = ca.create_control_app(mgr)
    handler = _extract_handler(
        app, "GET", "/processes/{process_id}/control"
    )
    req = _build_request(match_info={"process_id": "  "})
    req.app = {ca.CONTROL_KEY: mgr}
    resp = _run(handler(req))
    assert resp.status == 400


def test_request_kill_missing_process_id_returns_400():
    mgr = pc.ProcessControlManager(app_context=None)
    app = ca.create_control_app(mgr)
    handler = _extract_handler(
        app, "POST", "/processes/{process_id}/kill"
    )
    req = _build_request(method="POST", match_info={"process_id": ""})
    req.app = {ca.CONTROL_KEY: mgr}
    resp = _run(handler(req))
    assert resp.status == 400


def test_request_kill_swallows_malformed_json_body():
    mgr = pc.ProcessControlManager(app_context=None)
    app = ca.create_control_app(mgr)
    handler = _extract_handler(
        app, "POST", "/processes/{process_id}/kill"
    )
    req = _build_request(
        method="POST",
        match_info={"process_id": "p1"},
        can_read_body=True,
        json_raises=True,
    )
    req.app = {ca.CONTROL_KEY: mgr}
    resp = _run(handler(req))
    # Even though JSON parse failed, the kill request should still succeed (202)
    assert resp.status == 202


def test_request_kill_with_dict_body_uses_reason():
    mgr = pc.ProcessControlManager(app_context=None)
    app = ca.create_control_app(mgr)
    handler = _extract_handler(
        app, "POST", "/processes/{process_id}/kill"
    )
    req = _build_request(
        method="POST",
        match_info={"process_id": "p2"},
        can_read_body=True,
        json_value={"reason": "user-requested"},
    )
    req.app = {ca.CONTROL_KEY: mgr}
    resp = _run(handler(req))
    assert resp.status == 202
    assert _run(mgr.get("p2")).kill_reason == "user-requested"


def test_get_control_returns_record_payload_when_exists():
    mgr = pc.ProcessControlManager(app_context=None)
    _run(mgr.request_kill("pX", reason="explained"))
    app = ca.create_control_app(mgr)
    handler = _extract_handler(
        app, "GET", "/processes/{process_id}/control"
    )
    req = _build_request(match_info={"process_id": "pX"})
    req.app = {ca.CONTROL_KEY: mgr}
    resp = _run(handler(req))
    assert resp.status == 200
    assert b'"kill_requested": true' in resp.body
    assert b'"explained"' in resp.body


# ============== ControlApiServer lifecycle ==============


def test_control_api_server_disabled_start_is_noop():
    mgr = pc.ProcessControlManager(app_context=None)
    cfg = ca.ControlApiConfig(enabled=False)
    server = ca.ControlApiServer(mgr, cfg)
    _run(server.start())
    assert server._runner is None
    assert server._site is None


def test_control_api_server_start_and_stop():
    mgr = pc.ProcessControlManager(app_context=None)
    cfg = ca.ControlApiConfig(enabled=True, host="127.0.0.1", port=0)

    fake_runner = MagicMock()
    fake_runner.setup = AsyncMock()
    fake_runner.cleanup = AsyncMock()
    fake_site = MagicMock()
    fake_site.start = AsyncMock()
    fake_site.stop = AsyncMock()

    with (
        patch.object(web, "AppRunner", return_value=fake_runner),
        patch.object(web, "TCPSite", return_value=fake_site),
    ):
        server = ca.ControlApiServer(mgr, cfg)
        _run(server.start())
        assert server._runner is fake_runner
        assert server._site is fake_site
        _run(server.stop())
        assert server._runner is None
        assert server._site is None
    fake_runner.setup.assert_awaited_once()
    fake_site.start.assert_awaited_once()
    fake_site.stop.assert_awaited_once()
    fake_runner.cleanup.assert_awaited_once()


def test_control_api_server_stop_swallows_site_and_runner_exceptions():
    mgr = pc.ProcessControlManager(app_context=None)
    cfg = ca.ControlApiConfig(enabled=True)
    server = ca.ControlApiServer(mgr, cfg)
    server._site = MagicMock()
    server._site.stop = AsyncMock(side_effect=Exception("boom"))
    server._runner = MagicMock()
    server._runner.cleanup = AsyncMock(side_effect=Exception("boom"))
    # Should not raise
    _run(server.stop())
    assert server._site is None
    assert server._runner is None


def test_control_api_server_stop_when_not_started():
    mgr = pc.ProcessControlManager(app_context=None)
    cfg = ca.ControlApiConfig()
    server = ca.ControlApiServer(mgr, cfg)
    _run(server.stop())  # noop, no error
