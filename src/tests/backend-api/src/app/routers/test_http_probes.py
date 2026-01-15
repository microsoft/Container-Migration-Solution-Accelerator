"""
Unit tests for http_probes router.

This module contains comprehensive test cases for the HTTP probes endpoints
including health checks, startup probes, and root endpoint functionality.
"""

import datetime
import pytest
from unittest.mock import patch, Mock
from fastapi import Response
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

# Import the router and start_time from the module under test
from app.routers.http_probes import router, start_time, root, ImAlive, Startup


class TestHttpProbesRouter:
    """Base test class for HTTP probes router tests."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(router)
        # Create a fixed datetime for consistent testing
        self.fixed_datetime = datetime.datetime(2024, 1, 15, 12, 0, 0)
        self.mock_response = Mock(spec=Response)
        self.mock_response.headers = {}


class TestRootEndpoint(TestHttpProbesRouter):
    """Test cases for the root endpoint (/)."""

    @pytest.mark.asyncio
    async def test_root_success(self):
        """Test root endpoint returns correct response format."""
        with patch('app.routers.http_probes.datetime') as mock_datetime:
            mock_datetime.datetime.now.return_value = self.fixed_datetime
            
            result = await root()
            
            assert isinstance(result, JSONResponse)
            
            # Extract content from JSONResponse
            content = result.body.decode('utf-8')
            import json
            response_data = json.loads(content)
            
            assert response_data["message"] == "Code Migration Code converting process API"
            assert response_data["version"] == "1.0.0"
            assert response_data["status"] == "running"
            assert response_data["timestamp"] == self.fixed_datetime.isoformat()
            assert "uptime_seconds" in response_data
            assert isinstance(response_data["uptime_seconds"], (int, float))

    @pytest.mark.asyncio
    async def test_root_uptime_calculation(self):
        """Test root endpoint calculates uptime correctly."""
        # Mock start_time to be 1 hour ago
        mock_start_time = datetime.datetime(2024, 1, 15, 11, 0, 0)
        current_time = datetime.datetime(2024, 1, 15, 12, 0, 0)
        
        with patch('app.routers.http_probes.datetime') as mock_datetime:
            with patch('app.routers.http_probes.start_time', mock_start_time):
                mock_datetime.datetime.now.return_value = current_time
                
                result = await root()
                content = result.body.decode('utf-8')
                import json
                response_data = json.loads(content)
                
                # Should be 3600 seconds (1 hour)
                assert response_data["uptime_seconds"] == 3600.0

    def test_root_endpoint_via_client(self):
        """Test root endpoint through FastAPI test client."""
        response = self.client.get("/")
        
        assert response.status_code == 200
        
        response_data = response.json()
        assert response_data["message"] == "Code Migration Code converting process API"
        assert response_data["version"] == "1.0.0"
        assert response_data["status"] == "running"
        assert "timestamp" in response_data
        assert "uptime_seconds" in response_data


class TestHealthEndpoint(TestHttpProbesRouter):
    """Test cases for the health endpoint (/health)."""

    @pytest.mark.asyncio
    async def test_health_success(self):
        """Test health endpoint returns correct response and headers."""
        result = await ImAlive(self.mock_response)
        
        assert isinstance(result, JSONResponse)
        
        # Check that custom header was set
        assert self.mock_response.headers["Custom-Header"] == "liveness probe"
        
        # Extract and verify content
        content = result.body.decode('utf-8')
        import json
        response_data = json.loads(content)
        
        assert response_data["message"] == "I'm alive!"

    @pytest.mark.asyncio
    async def test_health_header_setting(self):
        """Test health endpoint sets correct custom header."""
        mock_response = Mock(spec=Response)
        mock_response.headers = {}
        
        await ImAlive(mock_response)
        
        assert "Custom-Header" in mock_response.headers
        assert mock_response.headers["Custom-Header"] == "liveness probe"

    def test_health_endpoint_via_client(self):
        """Test health endpoint through FastAPI test client."""
        response = self.client.get("/health")
        
        assert response.status_code == 200
        
        response_data = response.json()
        assert response_data["message"] == "I'm alive!"
        
        # Note: Custom headers are set on the Response object passed to the function,
        # but TestClient doesn't expose them in the same way. This is tested separately.

    @pytest.mark.asyncio
    async def test_health_different_response_objects(self):
        """Test health endpoint works with different Response object states."""
        # Test with response that has existing headers
        mock_response_with_headers = Mock(spec=Response)
        mock_response_with_headers.headers = {"Existing-Header": "value"}
        
        await ImAlive(mock_response_with_headers)
        
        assert mock_response_with_headers.headers["Custom-Header"] == "liveness probe"
        assert mock_response_with_headers.headers["Existing-Header"] == "value"


class TestStartupEndpoint(TestHttpProbesRouter):
    """Test cases for the startup endpoint (/startup)."""

    @pytest.mark.asyncio
    async def test_startup_success(self):
        """Test startup endpoint returns correct response format."""
        with patch('app.routers.http_probes.datetime') as mock_datetime:
            with patch('app.routers.http_probes.start_time', 
                      datetime.datetime(2024, 1, 15, 10, 30, 45)):
                mock_datetime.datetime.now.return_value = datetime.datetime(2024, 1, 15, 12, 35, 50)
                
                result = await Startup(self.mock_response)
                
                assert isinstance(result, JSONResponse)
                
                # Check that custom header was set
                assert self.mock_response.headers["Custom-Header"] == "Startup probe"
                
                # Extract and verify content
                content = result.body.decode('utf-8')
                import json
                response_data = json.loads(content)
                
                # Should be 2:5:5 (2 hours, 5 minutes, 5 seconds)
                assert response_data["message"] == "Running for 2:5:5"

    @pytest.mark.asyncio
    async def test_startup_uptime_calculation_various_durations(self):
        """Test startup endpoint calculates uptime correctly for different durations."""
        test_cases = [
            # (start_time_offset_seconds, expected_format)
            (3665, "1:1:5"),      # 1 hour, 1 minute, 5 seconds
            (7265, "2:1:5"),      # 2 hours, 1 minute, 5 seconds  
            (125, "0:2:5"),       # 2 minutes, 5 seconds
            (45, "0:0:45"),       # 45 seconds
            (3600, "1:0:0"),      # Exactly 1 hour
            (60, "0:1:0"),        # Exactly 1 minute
        ]
        
        base_time = datetime.datetime(2024, 1, 15, 12, 0, 0)
        
        for offset_seconds, expected_format in test_cases:
            with patch('app.routers.http_probes.datetime') as mock_datetime:
                start_time_mock = base_time - datetime.timedelta(seconds=offset_seconds)
                with patch('app.routers.http_probes.start_time', start_time_mock):
                    mock_datetime.datetime.now.return_value = base_time
                    
                    result = await Startup(self.mock_response)
                    content = result.body.decode('utf-8')
                    import json
                    response_data = json.loads(content)
                    
                    assert response_data["message"] == f"Running for {expected_format}"

    @pytest.mark.asyncio
    async def test_startup_header_setting(self):
        """Test startup endpoint sets correct custom header."""
        mock_response = Mock(spec=Response)
        mock_response.headers = {}
        
        with patch('app.routers.http_probes.datetime') as mock_datetime:
            mock_datetime.datetime.now.return_value = self.fixed_datetime
            
            await Startup(mock_response)
            
            assert "Custom-Header" in mock_response.headers
            assert mock_response.headers["Custom-Header"] == "Startup probe"

    def test_startup_endpoint_via_client(self):
        """Test startup endpoint through FastAPI test client."""
        response = self.client.get("/startup")
        
        assert response.status_code == 200
        
        response_data = response.json()
        assert "Running for" in response_data["message"]
        assert ":" in response_data["message"]  # Should contain time format
        
        # Note: Custom headers are set on the Response object passed to the function,
        # but TestClient doesn't expose them in the same way. This is tested separately.

    @pytest.mark.asyncio
    async def test_startup_zero_uptime(self):
        """Test startup endpoint with zero uptime."""
        current_time = datetime.datetime(2024, 1, 15, 12, 0, 0)
        
        with patch('app.routers.http_probes.datetime') as mock_datetime:
            with patch('app.routers.http_probes.start_time', current_time):
                mock_datetime.datetime.now.return_value = current_time
                
                result = await Startup(self.mock_response)
                content = result.body.decode('utf-8')
                import json
                response_data = json.loads(content)
                
                assert response_data["message"] == "Running for 0:0:0"


class TestRouterConfiguration(TestHttpProbesRouter):
    """Test cases for router configuration and metadata."""

    def test_router_tags(self):
        """Test router has correct tags configuration."""
        assert router.tags == ["http_probes"]

    def test_router_responses(self):
        """Test router has correct response configuration."""
        assert router.responses == {404: {"description": "Not found"}}

    def test_all_endpoints_accessible(self):
        """Test all endpoints are accessible through the router."""
        response_root = self.client.get("/")
        response_health = self.client.get("/health")
        response_startup = self.client.get("/startup")
        
        assert response_root.status_code == 200
        assert response_health.status_code == 200  
        assert response_startup.status_code == 200


class TestStartTimeVariable(TestHttpProbesRouter):
    """Test cases for the start_time global variable."""

    def test_start_time_is_datetime(self):
        """Test start_time is a datetime object."""
        from app.routers.http_probes import start_time
        assert isinstance(start_time, datetime.datetime)

    def test_start_time_is_reasonable(self):
        """Test start_time is within reasonable bounds (not in future, not too old)."""
        from app.routers.http_probes import start_time
        now = datetime.datetime.now()
        
        # Should not be in the future
        assert start_time <= now
        
        # Should not be more than 24 hours old (reasonable for a running service)
        one_day_ago = now - datetime.timedelta(days=1)
        assert start_time >= one_day_ago


class TestIntegrationScenarios(TestHttpProbesRouter):
    """Integration test scenarios for HTTP probes."""

    def test_all_endpoints_return_json(self):
        """Test that all endpoints return valid JSON responses."""
        endpoints = ["/", "/health", "/startup"]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            assert response.status_code == 200
            
            # Should be able to parse as JSON
            response_data = response.json()
            assert isinstance(response_data, dict)
            assert "message" in response_data

    def test_endpoints_response_format_consistency(self):
        """Test response format consistency across endpoints."""
        health_response = self.client.get("/health")
        startup_response = self.client.get("/startup")
        root_response = self.client.get("/")
        
        # All should return 200 OK
        assert health_response.status_code == 200
        assert startup_response.status_code == 200
        assert root_response.status_code == 200
        
        # All should return JSON with a message field
        health_data = health_response.json()
        startup_data = startup_response.json()
        root_data = root_response.json()
        
        assert "message" in health_data
        assert "message" in startup_data
        assert "message" in root_data

    @pytest.mark.asyncio
    async def test_time_consistency_across_endpoints(self):
        """Test time-related calculations are consistent across endpoints."""
        fixed_time = datetime.datetime(2024, 1, 15, 12, 0, 0)
        mock_start_time = datetime.datetime(2024, 1, 15, 10, 0, 0)  # 2 hours ago
        
        with patch('app.routers.http_probes.datetime') as mock_datetime:
            with patch('app.routers.http_probes.start_time', mock_start_time):
                mock_datetime.datetime.now.return_value = fixed_time
                
                # Test root endpoint uptime
                root_result = await root()
                root_content = root_result.body.decode('utf-8')
                import json
                root_data = json.loads(root_content)
                
                # Test startup endpoint uptime
                startup_result = await Startup(self.mock_response)
                startup_content = startup_result.body.decode('utf-8')
                startup_data = json.loads(startup_content)
                
                # Both should reflect the same 2-hour uptime
                assert root_data["uptime_seconds"] == 7200.0  # 2 hours in seconds
                assert startup_data["message"] == "Running for 2:0:0"