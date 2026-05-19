import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from libs.services.implementations import (
    ConsoleLoggerService,
    HttpClientService,
    InMemoryDataService,
)
from libs.services.interfaces import IDataService, IHttpService, ILoggerService


class TestInMemoryDataService:
    def test_get_returns_empty_dict_for_unknown_key(self):
        service = InMemoryDataService()
        assert service.get_data("missing") == {}

    def test_save_then_get_roundtrip(self):
        service = InMemoryDataService()
        assert service.save_data("k", {"a": 1}) is True
        assert service.get_data("k") == {"a": 1}

    def test_save_overwrites_existing_value(self):
        service = InMemoryDataService()
        service.save_data("k", {"a": 1})
        service.save_data("k", {"b": 2})
        assert service.get_data("k") == {"b": 2}

    def test_implements_interface(self):
        assert isinstance(InMemoryDataService(), IDataService)


class TestConsoleLoggerService:
    def test_log_info_writes_to_underlying_logger(self, caplog):
        service = ConsoleLoggerService()
        with caplog.at_level(logging.INFO, logger="ConsoleLoggerService"):
            service.log_info("hello")
        assert any("hello" in r.message for r in caplog.records)

    def test_log_error_with_exception_includes_exception(self, caplog):
        service = ConsoleLoggerService()
        with caplog.at_level(logging.ERROR, logger="ConsoleLoggerService"):
            service.log_error("boom", ValueError("bad"))
        assert any("boom" in r.message and "bad" in r.message for r in caplog.records)

    def test_log_error_without_exception(self, caplog):
        service = ConsoleLoggerService()
        with caplog.at_level(logging.ERROR, logger="ConsoleLoggerService"):
            service.log_error("only message")
        assert any("only message" in r.message for r in caplog.records)

    def test_implements_interface(self):
        assert isinstance(ConsoleLoggerService(), ILoggerService)


def _build_response(json_data=None, text="ok", content_type="application/json"):
    response = MagicMock()
    response.headers = {"content-type": content_type}
    response.json.return_value = json_data or {}
    response.text = text
    response.raise_for_status = MagicMock()
    return response


class TestHttpClientService:
    def test_implements_interface(self):
        assert isinstance(HttpClientService(), IHttpService)

    def test_get_returns_json_when_content_type_is_json(self):
        service = HttpClientService()
        response = _build_response(json_data={"ok": True})
        service._client.get = AsyncMock(return_value=response)
        result = asyncio.run(service.get("http://x"))
        assert result == {"ok": True}

    def test_get_returns_text_when_content_type_not_json(self):
        service = HttpClientService()
        response = _build_response(text="plain", content_type="text/plain")
        service._client.get = AsyncMock(return_value=response)
        result = asyncio.run(service.get("http://x"))
        assert result == {"text": "plain"}

    def test_get_returns_error_dict_on_exception(self):
        service = HttpClientService()
        service._client.get = AsyncMock(side_effect=RuntimeError("boom"))
        result = asyncio.run(service.get("http://x"))
        assert result == {"error": "boom"}

    def test_post_returns_json_when_content_type_is_json(self):
        service = HttpClientService()
        response = _build_response(json_data={"created": 1})
        service._client.post = AsyncMock(return_value=response)
        result = asyncio.run(service.post("http://x", {"a": 1}))
        assert result == {"created": 1}

    def test_post_returns_text_when_content_type_not_json(self):
        service = HttpClientService()
        response = _build_response(text="done", content_type="text/plain")
        service._client.post = AsyncMock(return_value=response)
        result = asyncio.run(service.post("http://x", {"a": 1}))
        assert result == {"text": "done"}

    def test_post_returns_error_dict_on_exception(self):
        service = HttpClientService()
        service._client.post = AsyncMock(side_effect=RuntimeError("nope"))
        result = asyncio.run(service.post("http://x", {}))
        assert result == {"error": "nope"}

    def test_async_context_manager_closes_client(self):
        service = HttpClientService()
        service._client.aclose = AsyncMock()

        async def run():
            async with service as s:
                assert s is service

        asyncio.run(run())
        service._client.aclose.assert_awaited_once()


class TestInterfacesAreAbstract:
    def test_idata_service_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            IDataService()

    def test_ilogger_service_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            ILoggerService()

    def test_ihttp_service_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            IHttpService()
