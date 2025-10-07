# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
from typing import Any, Dict

import httpx
from libs.services.interfaces import IDataService, IHttpService, ILoggerService


class InMemoryDataService(IDataService):
    """
    In-memory implementation of data service.
    """

    def __init__(self):
        self._data: Dict[str, Dict[str, Any]] = {}
        print(f"InMemoryDataService instance created: {id(self)}")

    def get_data(self, key: str) -> Dict[str, Any]:
        """Get data by key"""
        return self._data.get(key, {})

    def save_data(self, key: str, data: Dict[str, Any]) -> bool:
        """Save data with key"""
        self._data[key] = data
        return True


class ConsoleLoggerService(ILoggerService):
    """
    Console implementation of logger service.
    """

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        print(f"ConsoleLoggerService instance created: {id(self)}")

    def log_info(self, message: str) -> None:
        """Log info message"""
        self._logger.info(message)
        print(f"INFO: {message}")

    def log_error(self, message: str, exception: Exception = None) -> None:
        """Log error message"""
        if exception:
            self._logger.error(f"{message}: {exception}")
            print(f"ERROR: {message}: {exception}")
        else:
            self._logger.error(message)
            print(f"ERROR: {message}")


class HttpClientService(IHttpService):
    """
    HTTP client implementation using httpx.
    """

    def __init__(self):
        self._client = httpx.AsyncClient()
        print(f"HttpClientService instance created: {id(self)}")

    async def get(self, url: str) -> Dict[str, Any]:
        """Make HTTP GET request"""
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            return (
                response.json()
                if response.headers.get("content-type", "").startswith(
                    "application/json"
                )
                else {"text": response.text}
            )
        except Exception as e:
            return {"error": str(e)}

    async def post(self, url: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP POST request"""
        try:
            response = await self._client.post(url, json=data)
            response.raise_for_status()
            return (
                response.json()
                if response.headers.get("content-type", "").startswith(
                    "application/json"
                )
                else {"text": response.text}
            )
        except Exception as e:
            return {"error": str(e)}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()

