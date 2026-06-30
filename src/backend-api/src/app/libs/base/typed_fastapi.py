# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from fastapi import FastAPI
from libs.application.application_context import AppContext


class TypedFastAPI(FastAPI):
    """
    Extended FastAPI class with strongly typed app_context.
    This provides better IntelliSense and type checking in VS Code.
    """

    app_context: AppContext | None = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app_context: AppContext | None = None

    def set_app_context(self, app_context: AppContext) -> None:
        """
        Set the application context with proper typing.

        Args:
            app_context (AppContext): The application context to set
        """
        self.app_context = app_context
