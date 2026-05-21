# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio
from types import SimpleNamespace

import libs.agent_framework.middlewares as middlewares_module

ROLE_USER = "user"


class Message:
    def __init__(self, *, role, text=None, contents=None, author_name=None):
        self.role = role
        self.text = text
        self.contents = contents
        self.author_name = author_name


middlewares_module.Message = Message
from libs.agent_framework.middlewares import InputObserverMiddleware


def test_input_observer_middleware_replaces_user_text_when_configured() -> None:
    async def _run() -> None:
        ctx = SimpleNamespace(
            messages=[
                Message(role=ROLE_USER, text="original"),
            ]
        )

        mw = InputObserverMiddleware(replacement="replacement")

        async def _next(_context):
            return None

        await mw.process(ctx, _next)

        assert ctx.messages[0].role == ROLE_USER
        assert ctx.messages[0].text == "replacement"

    asyncio.run(_run())
