# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any
import httpx

from app.libs.services.implementations import (
    InMemoryDataService, 
    ConsoleLoggerService, 
    HttpClientService
)


class TestInMemoryDataService:
    """Test cases for InMemoryDataService class."""
    
    def test_init(self, capsys):
        """Test initialization of InMemoryDataService."""
        service = InMemoryDataService()
        
        # Check that the data dictionary is initialized
        assert service._data == {}
        
        # Check that initialization message is printed
        captured = capsys.readouterr()
        assert "InMemoryDataService instance created:" in captured.out
    
    def test_get_data_existing_key(self):
        """Test getting data for an existing key."""
        service = InMemoryDataService()
        test_data = {"name": "test", "value": 123}
        service._data["test_key"] = test_data
        
        result = service.get_data("test_key")
        
        assert result == test_data
    
    def test_get_data_non_existing_key(self):
        """Test getting data for a non-existing key."""
        service = InMemoryDataService()
        
        result = service.get_data("non_existing_key")
        
        assert result == {}
    
    def test_save_data(self):
        """Test saving data."""
        service = InMemoryDataService()
        test_data = {"name": "test", "value": 456}
        
        result = service.save_data("test_key", test_data)
        
        assert result is True
        assert service._data["test_key"] == test_data
    
    def test_save_data_overwrite(self):
        """Test overwriting existing data."""
        service = InMemoryDataService()
        original_data = {"name": "original", "value": 123}
        new_data = {"name": "new", "value": 456}
        
        service.save_data("test_key", original_data)
        result = service.save_data("test_key", new_data)
        
        assert result is True
        assert service._data["test_key"] == new_data
    
    def test_multiple_keys(self):
        """Test handling multiple keys."""
        service = InMemoryDataService()
        data1 = {"key1": "value1"}
        data2 = {"key2": "value2"}
        
        service.save_data("key1", data1)
        service.save_data("key2", data2)
        
        assert service.get_data("key1") == data1
        assert service.get_data("key2") == data2


class TestConsoleLoggerService:
    """Test cases for ConsoleLoggerService class."""
    
    @patch('logging.getLogger')
    def test_init(self, mock_get_logger, capsys):
        """Test initialization of ConsoleLoggerService."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        service = ConsoleLoggerService()
        
        # Check that logger is properly initialized
        mock_get_logger.assert_called_once_with('ConsoleLoggerService')
        assert service._logger == mock_logger
        
        # Check that initialization message is printed
        captured = capsys.readouterr()
        assert "ConsoleLoggerService instance created:" in captured.out
    
    @patch('logging.getLogger')
    def test_log_info(self, mock_get_logger, capsys):
        """Test logging info message."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        service = ConsoleLoggerService()
        test_message = "Test info message"
        
        service.log_info(test_message)
        
        # Check that logger.info was called
        mock_logger.info.assert_called_once_with(test_message)
        
        # Check that message was printed to console
        captured = capsys.readouterr()
        assert f"INFO: {test_message}" in captured.out
    
    @patch('logging.getLogger')
    def test_log_error_without_exception(self, mock_get_logger, capsys):
        """Test logging error message without exception."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        service = ConsoleLoggerService()
        test_message = "Test error message"
        
        service.log_error(test_message)
        
        # Check that logger.error was called
        mock_logger.error.assert_called_once_with(test_message)
        
        # Check that message was printed to console
        captured = capsys.readouterr()
        assert f"ERROR: {test_message}" in captured.out
    
    @patch('logging.getLogger')
    def test_log_error_with_exception(self, mock_get_logger, capsys):
        """Test logging error message with exception."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        service = ConsoleLoggerService()
        test_message = "Test error message"
        test_exception = ValueError("Test exception")
        
        service.log_error(test_message, test_exception)
        
        # Check that logger.error was called with exception
        expected_message = f"{test_message}: {test_exception}"
        mock_logger.error.assert_called_once_with(expected_message)
        
        # Check that message was printed to console
        captured = capsys.readouterr()
        assert f"ERROR: {expected_message}" in captured.out
    
    @patch('logging.getLogger')
    def test_log_error_with_none_exception(self, mock_get_logger, capsys):
        """Test logging error message with None exception."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        service = ConsoleLoggerService()
        test_message = "Test error message"
        
        service.log_error(test_message, None)
        
        # Check that logger.error was called without exception
        mock_logger.error.assert_called_once_with(test_message)
        
        # Check that message was printed to console
        captured = capsys.readouterr()
        assert f"ERROR: {test_message}" in captured.out


class TestHttpClientService:
    """Test cases for HttpClientService class."""
    
    @patch('httpx.AsyncClient')
    def test_init(self, mock_async_client, capsys):
        """Test initialization of HttpClientService."""
        mock_client = Mock()
        mock_async_client.return_value = mock_client
        
        service = HttpClientService()
        
        # Check that AsyncClient was created
        mock_async_client.assert_called_once()
        assert service._client == mock_client
        
        # Check that initialization message is printed
        captured = capsys.readouterr()
        assert "HttpClientService instance created:" in captured.out
    
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_get_success_json_response(self, mock_async_client):
        """Test successful GET request with JSON response."""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {"key": "value"}
        mock_response.headers.get.return_value = "application/json"
        mock_response.raise_for_status.return_value = None
        
        # Mock client
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_async_client.return_value = mock_client
        
        service = HttpClientService()
        
        result = await service.get("http://example.com")
        
        # Check that request was made
        mock_client.get.assert_called_once_with("http://example.com")
        
        # Check response
        assert result == {"key": "value"}
    
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_get_success_text_response(self, mock_async_client):
        """Test successful GET request with text response."""
        # Mock response
        mock_response = Mock()
        mock_response.text = "plain text response"
        mock_response.headers.get.return_value = "text/plain"
        mock_response.raise_for_status.return_value = None
        
        # Mock client
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_async_client.return_value = mock_client
        
        service = HttpClientService()
        
        result = await service.get("http://example.com")
        
        # Check that request was made
        mock_client.get.assert_called_once_with("http://example.com")
        
        # Check response
        assert result == {"text": "plain text response"}
    
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_get_exception(self, mock_async_client):
        """Test GET request with exception."""
        # Mock client to raise exception
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.HTTPError("Connection error")
        mock_async_client.return_value = mock_client
        
        service = HttpClientService()
        
        result = await service.get("http://example.com")
        
        # Check that error is returned
        assert "error" in result
        assert "Connection error" in result["error"]
    
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_get_http_status_error(self, mock_async_client):
        """Test GET request with HTTP status error."""
        # Mock response that raises status error
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=Mock(), response=Mock()
        )
        
        # Mock client
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_async_client.return_value = mock_client
        
        service = HttpClientService()
        
        result = await service.get("http://example.com/notfound")
        
        # Check that error is returned
        assert "error" in result
        assert "404 Not Found" in result["error"]
    
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_post_success_json_response(self, mock_async_client):
        """Test successful POST request with JSON response."""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {"result": "success"}
        mock_response.headers.get.return_value = "application/json"
        mock_response.raise_for_status.return_value = None
        
        # Mock client
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_async_client.return_value = mock_client
        
        service = HttpClientService()
        test_data = {"input": "test"}
        
        result = await service.post("http://example.com/api", test_data)
        
        # Check that request was made
        mock_client.post.assert_called_once_with("http://example.com/api", json=test_data)
        
        # Check response
        assert result == {"result": "success"}
    
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_post_success_text_response(self, mock_async_client):
        """Test successful POST request with text response."""
        # Mock response
        mock_response = Mock()
        mock_response.text = "success"
        mock_response.headers.get.return_value = "text/plain"
        mock_response.raise_for_status.return_value = None
        
        # Mock client
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_async_client.return_value = mock_client
        
        service = HttpClientService()
        test_data = {"input": "test"}
        
        result = await service.post("http://example.com/api", test_data)
        
        # Check that request was made
        mock_client.post.assert_called_once_with("http://example.com/api", json=test_data)
        
        # Check response
        assert result == {"text": "success"}
    
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_post_exception(self, mock_async_client):
        """Test POST request with exception."""
        # Mock client to raise exception
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.HTTPError("Server error")
        mock_async_client.return_value = mock_client
        
        service = HttpClientService()
        test_data = {"input": "test"}
        
        result = await service.post("http://example.com/api", test_data)
        
        # Check that error is returned
        assert "error" in result
        assert "Server error" in result["error"]
    
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_post_http_status_error(self, mock_async_client):
        """Test POST request with HTTP status error."""
        # Mock response that raises status error
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Server Error", request=Mock(), response=Mock()
        )
        
        # Mock client
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_async_client.return_value = mock_client
        
        service = HttpClientService()
        test_data = {"input": "test"}
        
        result = await service.post("http://example.com/api", test_data)
        
        # Check that error is returned
        assert "error" in result
        assert "500 Server Error" in result["error"]
    
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_async_context_manager_enter(self, mock_async_client):
        """Test async context manager __aenter__ method."""
        mock_client = Mock()
        mock_async_client.return_value = mock_client
        
        service = HttpClientService()
        
        result = await service.__aenter__()
        
        # Check that service returns itself
        assert result is service
    
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_async_context_manager_exit(self, mock_async_client):
        """Test async context manager __aexit__ method."""
        mock_client = AsyncMock()
        mock_async_client.return_value = mock_client
        
        service = HttpClientService()
        
        await service.__aexit__(None, None, None)
        
        # Check that client was closed
        mock_client.aclose.assert_called_once()
    
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_async_context_manager_exit_with_exception(self, mock_async_client):
        """Test async context manager __aexit__ method with exception."""
        mock_client = AsyncMock()
        mock_async_client.return_value = mock_client
        
        service = HttpClientService()
        
        # Test with exception parameters
        exc_type = ValueError
        exc_val = ValueError("Test exception")
        exc_tb = None
        
        await service.__aexit__(exc_type, exc_val, exc_tb)
        
        # Check that client was closed even with exception
        mock_client.aclose.assert_called_once()
    
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_full_async_context_manager_usage(self, mock_async_client):
        """Test full async context manager usage."""
        mock_client = AsyncMock()
        mock_async_client.return_value = mock_client
        
        async with HttpClientService() as service:
            # Service should be usable within context
            assert isinstance(service, HttpClientService)
            assert service._client == mock_client
        
        # Client should be closed after exiting context
        mock_client.aclose.assert_called_once()
    
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_get_json_response_edge_case(self, mock_async_client):
        """Test GET request with JSON content type variations."""
        # Test with application/json content type
        mock_response = Mock()
        mock_response.json.return_value = {"test": "data"}
        mock_response.headers.get.return_value = "application/json"
        mock_response.raise_for_status.return_value = None
        
        # Mock client
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_async_client.return_value = mock_client
        
        service = HttpClientService()
        
        result = await service.get("http://example.com")
        
        assert result == {"test": "data"}
        
        # Test with non-JSON content type
        mock_response.text = "plain text"
        mock_response.headers.get.return_value = "text/plain"
        
        result = await service.get("http://example.com")
        
        assert result == {"text": "plain text"}
    
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_get_empty_content_type(self, mock_async_client):
        """Test GET request with empty content type."""
        # Mock response with no content-type header (returns empty string)
        mock_response = Mock()
        mock_response.text = "plain response"
        mock_response.headers.get.return_value = ""
        mock_response.raise_for_status.return_value = None
        
        # Mock client
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_async_client.return_value = mock_client
        
        service = HttpClientService()
        
        result = await service.get("http://example.com")
        
        # Should return text response when no content-type
        assert result == {"text": "plain response"}