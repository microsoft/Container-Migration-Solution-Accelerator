# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Protocol

from fastapi import FastAPI
from libs.application.application_context import AppContext


class FastAPIWithContext(Protocol):
    """
    Protocol defining FastAPI with app_context.
    This provides type hints without subclassing.
    """

    app_context: AppContext

    # Include essential FastAPI methods for type checking
    def include_router(self, *args, **kwargs) -> None:
        ...


def add_app_context_to_fastapi(
    app: FastAPI, app_context: AppContext
) -> FastAPIWithContext:
    """
    Add app_context to FastAPI instance with proper typing.

    Args:
        app: FastAPI instance
        app_context: Application context to attach

    Returns:
        FastAPI instance with app_context (typed as FastAPIWithContext)
    """
    app.app_context = app_context  # type: ignore
    return app  # type: ignore
