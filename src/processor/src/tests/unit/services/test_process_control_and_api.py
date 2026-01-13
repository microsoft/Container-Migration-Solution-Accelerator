# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio

import aiohttp
from aiohttp import web

from services.control_api import create_control_app
from services.process_control import ProcessControlManager


def test_process_control_manager_in_memory_lifecycle():
    async def _run():
        mgr = ProcessControlManager(app_context=None)

        rec = await mgr.request_kill("p1", reason="test")
        assert rec.id == "p1"
        assert rec.kill_requested is True
        assert rec.kill_state == "pending"
        assert rec.kill_reason == "test"

        await mgr.ack_executing("p1", instance_id="instance-1")
        rec2 = await mgr.get("p1")
        assert rec2 is not None
        assert rec2.kill_state == "executing"
        assert rec2.kill_ack_instance_id == "instance-1"

        await mgr.mark_executed("p1", instance_id="instance-1")
        rec3 = await mgr.get("p1")
        assert rec3 is not None
        assert rec3.kill_state == "executed"
        assert rec3.kill_executed_at

    asyncio.run(_run())


def test_control_api_kill_and_get_control_no_auth():
    async def _run():
        mgr = ProcessControlManager(app_context=None)
        app = create_control_app(mgr, bearer_token="")

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="127.0.0.1", port=0)
        await site.start()

        # Determine the chosen ephemeral port
        sites = list(runner.sites)
        assert sites
        server = next(iter(sites))._server  # type: ignore[attr-defined]
        port = server.sockets[0].getsockname()[1]

        base = f"http://127.0.0.1:{port}"

        async with aiohttp.ClientSession() as session:
            # initially missing
            async with session.get(f"{base}/processes/p1/control") as resp:
                assert resp.status == 200
                body = await resp.json()
                assert body["exists"] is False

            # request kill
            async with session.post(
                f"{base}/processes/p1/kill", json={"reason": "api"}
            ) as resp:
                assert resp.status == 202
                body = await resp.json()
                assert body["kill_state"] == "pending"

            # fetch control
            async with session.get(f"{base}/processes/p1/control") as resp:
                assert resp.status == 200
                body = await resp.json()
                assert body["exists"] is True
                assert body["kill_requested"] is True
                assert body["kill_reason"] == "api"

        await runner.cleanup()

    asyncio.run(_run())


def test_control_api_requires_bearer_token_when_configured():
    async def _run():
        mgr = ProcessControlManager(app_context=None)
        app = create_control_app(mgr, bearer_token="secret")

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="127.0.0.1", port=0)
        await site.start()

        sites = list(runner.sites)
        assert sites
        server = next(iter(sites))._server  # type: ignore[attr-defined]
        port = server.sockets[0].getsockname()[1]

        base = f"http://127.0.0.1:{port}"

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{base}/processes/p1/kill") as resp:
                assert resp.status == 401

            async with session.post(
                f"{base}/processes/p1/kill",
                headers={"Authorization": "Bearer secret"},
            ) as resp:
                assert resp.status == 202

        await runner.cleanup()

    asyncio.run(_run())
