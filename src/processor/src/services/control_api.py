# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Control API server (aiohttp).

This server exposes endpoints for managing processes in a replica-agnostic way.

Key idea:
- External callers write control intent (e.g., kill request) to a shared store.
- The owning queue worker instance (which has the process_id in-flight) observes
  that intent and executes the local hard-kill.

This avoids the need to route HTTP traffic to a specific ACA replica.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from aiohttp import web

from services.process_control import ProcessControlManager

logger = logging.getLogger(__name__)


# Use AppKey instead of string keys to avoid aiohttp NotAppKeyWarning.
CONTROL_KEY = web.AppKey("control", ProcessControlManager)


@dataclass
class ControlApiConfig:
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8080
    bearer_token: str = ""


def _json_response(payload: dict[str, Any], status: int = 200) -> web.Response:
    return web.Response(
        text=json.dumps(payload, ensure_ascii=False),
        status=status,
        content_type="application/json",
    )


def create_control_app(
    control: ProcessControlManager, bearer_token: str = ""
) -> web.Application:
    """Create an aiohttp web app for process control."""

    @web.middleware
    async def _auth_middleware(request: web.Request, handler):
        if bearer_token:
            auth = request.headers.get("Authorization", "")
            if auth != f"Bearer {bearer_token}":
                return _json_response({"error": "unauthorized"}, status=401)
        return await handler(request)

    app = web.Application(middlewares=[_auth_middleware])
    app[CONTROL_KEY] = control

    async def health(_request: web.Request) -> web.Response:
        return _json_response({"status": "ok"})

    async def get_control(request: web.Request) -> web.Response:
        process_id = request.match_info.get("process_id", "").strip()
        if not process_id:
            return _json_response({"error": "missing process_id"}, status=400)

        record = await request.app[CONTROL_KEY].get(process_id)
        if not record:
            return _json_response(
                {"process_id": process_id, "exists": False}, status=200
            )

        return _json_response(
            {
                "process_id": record.id,
                "exists": True,
                "kill_requested": record.kill_requested,
                "kill_requested_at": record.kill_requested_at,
                "kill_reason": record.kill_reason,
                "kill_state": record.kill_state,
                "kill_ack_instance_id": record.kill_ack_instance_id,
                "kill_ack_at": record.kill_ack_at,
                "kill_executed_at": record.kill_executed_at,
                "last_update_time": record.last_update_time,
            }
        )

    async def request_kill(request: web.Request) -> web.Response:
        process_id = request.match_info.get("process_id", "").strip()
        if not process_id:
            return _json_response({"error": "missing process_id"}, status=400)

        reason = ""
        if request.can_read_body:
            try:
                body = await request.json()
                if isinstance(body, dict):
                    reason = str(body.get("reason", "") or "")
            except Exception:
                # Ignore malformed JSON; kill request can still be accepted.
                pass

        record = await request.app[CONTROL_KEY].request_kill(process_id, reason=reason)
        return _json_response(
            {
                "process_id": record.id,
                "kill_requested": record.kill_requested,
                "kill_state": record.kill_state,
                "kill_requested_at": record.kill_requested_at,
            },
            status=202,
        )

    # Health probe endpoint
    app.router.add_get("/health", health)
    # Process status check endpoint
    app.router.add_get("/processes/{process_id}/control", get_control)
    # Process kill request endpoint
    app.router.add_post("/processes/{process_id}/kill", request_kill)

    return app


class ControlApiServer:
    """Lifecycle wrapper for running the aiohttp server inside the worker."""

    def __init__(self, control: ProcessControlManager, config: ControlApiConfig):
        self.control = control
        self.config = config
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    async def start(self) -> None:
        if not self.config.enabled:
            return

        app = create_control_app(self.control, bearer_token=self.config.bearer_token)
        self._runner = web.AppRunner(app)
        await self._runner.setup()

        self._site = web.TCPSite(
            self._runner, host=self.config.host, port=self.config.port
        )
        await self._site.start()

        logger.info(
            "Control API listening on http://%s:%s", self.config.host, self.config.port
        )

    async def stop(self) -> None:
        if self._site:
            try:
                await self._site.stop()
            except Exception:
                pass
            self._site = None

        if self._runner:
            try:
                await self._runner.cleanup()
            except Exception:
                pass
            self._runner = None
