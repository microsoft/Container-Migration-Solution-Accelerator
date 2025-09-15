# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from abc import ABC, abstractmethod
from typing import Any, Dict, Union


class IDataService(ABC):
    """
    Interface for data service operations.
    """

    @abstractmethod
    def get_data(self, key: str) -> Dict[str, Any]:
        """Get data by key"""
        pass

    @abstractmethod
    def save_data(self, key: str, data: Dict[str, Any]) -> bool:
        """Save data with key"""
        pass


class ILoggerService(ABC):
    """
    Interface for logging service operations.
    """

    @abstractmethod
    def log_info(self, message: str) -> None:
        """Log info message"""
        pass

    @abstractmethod
    def log_error(self, message: str, exception: Exception = None) -> None:
        """Log error message"""
        pass


class IHttpService(ABC):
    """
    Interface for HTTP service operations.
    """

    @abstractmethod
    async def get(self, url: str) -> Dict[str, Any]:
        """Make HTTP GET request"""
        pass

    @abstractmethod
    async def post(self, url: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP POST request"""
        pass