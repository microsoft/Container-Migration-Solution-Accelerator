# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio
from types import SimpleNamespace

import libs.agent_framework.middlewares as middlewares_module

ROLE_USER = "user"


class Message:
    """Test stub for Message - the real Message in 1.3.0 uses contents= instead of text=."""

    def __init__(self, *, role, text=None, contents=None, author_name=None):
        self.role = role
        self.text = text
        self.contents = contents
        self.author_name = author_name


# Patch at module level: middleware code references Message at runtime for isinstance
# checks and construction. This is scoped to test execution only.
_original_message = getattr(middlewares_module, "Message", None)
middlewares_module.Message = Message
from libs.agent_framework.middlewares import InputObserverMiddleware  # noqa: E402


def teardown_module(module=None):
    """Restore the original Message class to avoid leaking into other tests."""
    if _original_message is not None:
        middlewares_module.Message = _original_message


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
