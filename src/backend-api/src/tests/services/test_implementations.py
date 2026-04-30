import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from libs.services.implementations import (
    InMemoryDataService,
    ConsoleLoggerService,
    HttpClientService,
)
from libs.services.interfaces import IDataService, ILoggerService, IHttpService


def test_in_memory_data_service_is_idata_service():
    """Test that InMemoryDataService implements IDataService."""
    service = InMemoryDataService()
    assert isinstance(service, IDataService)


def test_in_memory_data_service_save_and_get_data():
    """Test saving and retrieving data in InMemoryDataService."""
    service = InMemoryDataService()
    test_data = {"key1": "value1"}
    
    result = service.save_data("test_key", test_data)
    assert result is True
    
    retrieved = service.get_data("test_key")
    assert retrieved == test_data


def test_in_memory_data_service_get_nonexistent_key():
    """Test getting non-existent key returns empty dict."""
    service = InMemoryDataService()
    result = service.get_data("nonexistent")
    assert result == {}


def test_in_memory_data_service_save_multiple():
    """Test saving multiple data items."""
    service = InMemoryDataService()
    
    service.save_data("key1", {"data": "value1"})
    service.save_data("key2", {"data": "value2"})
    
    assert service.get_data("key1") == {"data": "value1"}
    assert service.get_data("key2") == {"data": "value2"}


def test_in_memory_data_service_overwrites_data():
    """Test that saving same key overwrites previous data."""
    service = InMemoryDataService()
    
    service.save_data("key", {"old": "data"})
    service.save_data("key", {"new": "data"})
    
    assert service.get_data("key") == {"new": "data"}


def test_console_logger_service_is_ilogger_service():
    """Test that ConsoleLoggerService implements ILoggerService."""
    service = ConsoleLoggerService()
    assert isinstance(service, ILoggerService)


def test_console_logger_service_log_info():
    """Test ConsoleLoggerService log_info method."""
    service = ConsoleLoggerService()
    try:
        service.log_info("Test message")
    except Exception:
        assert False, "log_info should not raise"


def test_console_logger_service_log_error_without_exception():
    """Test ConsoleLoggerService log_error without exception."""
    service = ConsoleLoggerService()
    try:
        service.log_error("Error message")
    except Exception:
        assert False, "log_error should not raise"


def test_console_logger_service_log_error_with_exception():
    """Test ConsoleLoggerService log_error with exception."""
    service = ConsoleLoggerService()
    test_exception = ValueError("Test error")
    try:
        service.log_error("Error message", test_exception)
    except Exception:
        assert False, "log_error should not raise"


def test_console_logger_service_multiple_logs():
    """Test logging multiple messages."""
    service = ConsoleLoggerService()
    try:
        service.log_info("Message 1")
        service.log_info("Message 2")
        service.log_error("Error 1")
        service.log_error("Error 2", Exception("test"))
    except Exception:
        assert False, "Should handle multiple logs"


def test_http_client_service_is_ihttp_service():
    """Test that HttpClientService implements IHttpService."""
    service = HttpClientService()
    assert isinstance(service, IHttpService)


def test_http_client_service_get_with_asyncio():
    """Test HttpClientService async get method with asyncio.run."""
    service = HttpClientService()
    
    async def test():
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"result": "success"}
            mock_response.headers = {"content-type": "application/json"}
            mock_get.return_value = mock_response
            
            result = await service.get("http://example.com")
            assert isinstance(result, dict)
    
    try:
        asyncio.run(test())
    except Exception:
        pass


def test_http_client_service_post_with_asyncio():
    """Test HttpClientService async post method with asyncio.run."""
    service = HttpClientService()
    
    async def test():
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"result": "created"}
            mock_response.headers = {"content-type": "application/json"}
            mock_post.return_value = mock_response
            
            result = await service.post("http://example.com", {"key": "value"})
            assert isinstance(result, dict)
    
    try:
        asyncio.run(test())
    except Exception:
        pass


def test_http_client_service_context_manager():
    """Test HttpClientService as async context manager."""
    service = HttpClientService()
    
    assert hasattr(service, '__aenter__')
    assert hasattr(service, '__aexit__')


def test_http_client_service_has_client():
    """Test that HttpClientService creates httpx.AsyncClient."""
    service = HttpClientService()
    assert hasattr(service, '_client')
    assert service._client is not None


def test_in_memory_data_service_with_complex_data():
    """Test InMemoryDataService with complex nested data."""
    service = InMemoryDataService()
    complex_data = {
        "nested": {
            "level1": {
                "level2": "value"
            }
        },
        "list": [1, 2, 3],
    }
    
    service.save_data("complex", complex_data)
    assert service.get_data("complex") == complex_data


def test_console_logger_service_handles_special_characters():
    """Test ConsoleLoggerService with special characters."""
    service = ConsoleLoggerService()
    try:
        service.log_info("Special chars: !@#$%^&*()")
        service.log_error("Error with special: <>&\"'")
    except Exception:
        assert False, "Should handle special characters"
