"""Tests for libs/services/interfaces.py.

These cover the abstract `pass` bodies of the interfaces by subclassing the
ABCs and calling the parent abstract methods via super(). The bodies are no-op
``pass`` statements, so the parent calls return ``None``; the goal is purely
to exercise those lines for coverage.
"""

from typing import Any, Dict

import pytest

from libs.services.interfaces import IDataService, IHttpService, ILoggerService


class _DataImpl(IDataService):
    def get_data(self, key: str) -> Dict[str, Any]:
        return super().get_data(key)

    def save_data(self, key: str, data: Dict[str, Any]) -> bool:
        return super().save_data(key, data)


class _LoggerImpl(ILoggerService):
    def log_info(self, message: str) -> None:
        return super().log_info(message)

    def log_error(self, message: str, exception: Exception = None) -> None:
        return super().log_error(message, exception)


class _HttpImpl(IHttpService):
    async def get(self, url: str) -> Dict[str, Any]:
        return await self._get_super(url)

    async def post(self, url: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._post_super(url, data)

    async def _get_super(self, url):
        return await IHttpService.get(self, url)

    async def _post_super(self, url, data):
        return await IHttpService.post(self, url, data)


class TestIDataService:
    def test_subclass_super_calls_return_none(self):
        impl = _DataImpl()
        assert impl.get_data("k") is None
        assert impl.save_data("k", {"a": 1}) is None


class TestILoggerService:
    def test_subclass_super_calls_return_none(self):
        impl = _LoggerImpl()
        assert impl.log_info("hello") is None
        assert impl.log_error("oops", ValueError("x")) is None
        assert impl.log_error("oops") is None


class TestIHttpService:
    @pytest.mark.asyncio
    async def test_subclass_super_calls_return_none(self):
        impl = _HttpImpl()
        assert await impl.get("https://x") is None
        assert await impl.post("https://x", {"a": 1}) is None


class TestAbstractInstantiation:
    def test_idataservice_cannot_be_instantiated_directly(self):
        with pytest.raises(TypeError):
            IDataService()  # type: ignore[abstract]

    def test_iloggerservice_cannot_be_instantiated_directly(self):
        with pytest.raises(TypeError):
            ILoggerService()  # type: ignore[abstract]

    def test_ihttpservice_cannot_be_instantiated_directly(self):
        with pytest.raises(TypeError):
            IHttpService()  # type: ignore[abstract]
