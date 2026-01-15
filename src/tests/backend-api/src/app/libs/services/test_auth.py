"""
Unit tests for auth.py module

This module contains comprehensive unit tests for the authentication functionality,
covering UserDetails class, tenant ID extraction, and user authentication from
request headers.
"""

import base64
import json
import logging
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import HTTPException, Request

# Import the classes and functions under test
from app.libs.services.auth import (
    UserDetails,
    get_tenant_id,
    get_authenticated_user,
    sample_user
)


class TestUserDetails:
    """Test cases for UserDetails class"""
    
    def test_init_with_empty_dict(self):
        """Test UserDetails initialization with empty dictionary"""
        user_details = UserDetails({})
        
        assert user_details.user_principal_id is None
        assert user_details.user_name is None
        assert user_details.auth_provider is None
        assert user_details.auth_token is None
        assert user_details.tenant_id is None

    def test_init_with_basic_user_details(self):
        """Test UserDetails initialization with basic user information"""
        user_data = {
            "user_principal_id": "test-user-id",
            "user_name": "test.user@example.com",
            "auth_provider": "aad",
            "auth_token": "test-token"
        }
        
        user_details = UserDetails(user_data)
        
        assert user_details.user_principal_id == "test-user-id"
        assert user_details.user_name == "test.user@example.com"
        assert user_details.auth_provider == "aad"
        assert user_details.auth_token == "test-token"
        assert user_details.tenant_id is None

    def test_init_with_client_principal_b64_sample_value(self):
        """Test initialization when client_principal_b64 has sample value"""
        user_data = {
            "user_principal_id": "test-user-id",
            "client_principal_b64": "your_base_64_encoded_token"
        }
        
        user_details = UserDetails(user_data)
        
        assert user_details.user_principal_id == "test-user-id"
        assert user_details.tenant_id is None

    @patch('app.libs.services.auth.get_tenant_id')
    def test_init_with_valid_client_principal_b64(self, mock_get_tenant_id):
        """Test initialization with valid client principal base64"""
        mock_get_tenant_id.return_value = "test-tenant-id"
        
        user_data = {
            "user_principal_id": "test-user-id",
            "client_principal_b64": "valid_base64_token"
        }
        
        user_details = UserDetails(user_data)
        
        assert user_details.user_principal_id == "test-user-id"
        assert user_details.tenant_id == "test-tenant-id"
        mock_get_tenant_id.assert_called_once_with("valid_base64_token")

    def test_init_with_none_client_principal_b64(self):
        """Test initialization when client_principal_b64 is None"""
        user_data = {
            "user_principal_id": "test-user-id",
            "client_principal_b64": None
        }
        
        user_details = UserDetails(user_data)
        
        assert user_details.user_principal_id == "test-user-id"
        assert user_details.tenant_id is None

    def test_init_with_partial_data(self):
        """Test initialization with some fields missing"""
        user_data = {
            "user_principal_id": "test-user-id",
            "auth_provider": "aad"
            # Missing user_name and auth_token
        }
        
        user_details = UserDetails(user_data)
        
        assert user_details.user_principal_id == "test-user-id"
        assert user_details.user_name is None
        assert user_details.auth_provider == "aad"
        assert user_details.auth_token is None
        assert user_details.tenant_id is None


class TestGetTenantId:
    """Test cases for get_tenant_id function"""
    
    def test_get_tenant_id_valid_base64_with_tid(self):
        """Test get_tenant_id with valid base64 containing tenant ID"""
        user_info = {"tid": "test-tenant-id", "sub": "test-subject"}
        json_string = json.dumps(user_info)
        base64_string = base64.b64encode(json_string.encode('utf-8')).decode('utf-8')
        
        result = get_tenant_id(base64_string)
        
        assert result == "test-tenant-id"

    def test_get_tenant_id_valid_base64_without_tid(self):
        """Test get_tenant_id with valid base64 but no tenant ID"""
        user_info = {"sub": "test-subject", "name": "Test User"}
        json_string = json.dumps(user_info)
        base64_string = base64.b64encode(json_string.encode('utf-8')).decode('utf-8')
        
        result = get_tenant_id(base64_string)
        
        assert result == ""

    def test_get_tenant_id_invalid_base64(self):
        """Test get_tenant_id with invalid base64 string"""
        invalid_base64 = "invalid_base64_string!"
        
        result = get_tenant_id(invalid_base64)
        
        assert result == ""

    def test_get_tenant_id_valid_base64_invalid_json(self):
        """Test get_tenant_id with valid base64 but invalid JSON"""
        invalid_json = "not a json string"
        base64_string = base64.b64encode(invalid_json.encode('utf-8')).decode('utf-8')
        
        result = get_tenant_id(base64_string)
        
        assert result == ""

    def test_get_tenant_id_empty_string(self):
        """Test get_tenant_id with empty string"""
        result = get_tenant_id("")
        
        assert result == ""

    def test_get_tenant_id_none_value(self):
        """Test get_tenant_id with None input - should return empty string"""
        result = get_tenant_id(None)
        
        assert result == ""

    @patch('app.libs.services.auth.logger')
    def test_get_tenant_id_logs_exception(self, mock_logger):
        """Test that get_tenant_id logs exceptions properly"""
        invalid_base64 = "invalid_base64_string!"
        
        result = get_tenant_id(invalid_base64)
        
        assert result == ""
        mock_logger.exception.assert_called_once_with("Error decoding client principal")

    def test_get_tenant_id_with_complex_json(self):
        """Test get_tenant_id with complex JSON structure"""
        user_info = {
            "tid": "complex-tenant-id",
            "sub": "test-subject",
            "claims": {
                "name": "Test User",
                "roles": ["admin", "user"]
            },
            "exp": 1234567890
        }
        json_string = json.dumps(user_info)
        base64_string = base64.b64encode(json_string.encode('utf-8')).decode('utf-8')
        
        result = get_tenant_id(base64_string)
        
        assert result == "complex-tenant-id"


class TestGetAuthenticatedUser:
    """Test cases for get_authenticated_user function"""
    
    def test_get_authenticated_user_with_production_headers(self):
        """Test get_authenticated_user with production-style headers"""
        # Create a mock request with headers
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "x-ms-client-principal-id": "prod-user-id",
            "x-ms-client-principal-name": "prod.user@example.com",
            "x-ms-client-principal-idp": "aad",
            "x-ms-token-aad-id-token": "prod-token"
        }
        
        result = get_authenticated_user(mock_request)
        
        assert isinstance(result, UserDetails)
        assert result.user_principal_id == "prod-user-id"

    @patch('app.libs.services.auth.logger')
    def test_get_authenticated_user_without_headers_uses_sample(self, mock_logger):
        """Test get_authenticated_user falls back to sample user when no headers"""
        # Create a mock request without authentication headers
        mock_request = Mock(spec=Request)
        mock_request.headers = {"content-type": "application/json"}
        
        result = get_authenticated_user(mock_request)
        
        assert isinstance(result, UserDetails)
        assert result.user_principal_id == sample_user["x-ms-client-principal-id"]
        mock_logger.info.assert_any_call("No user principal found in headers - using development user")

    def test_get_authenticated_user_with_mixed_case_headers(self):
        """Test get_authenticated_user with mixed case headers - falls back to sample user"""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "X-MS-CLIENT-PRINCIPAL-ID": "mixed-case-user-id",  # Wrong case, won't match exact key check
            "x-ms-CLIENT-principal-name": "mixed.user@example.com"
        }
        
        result = get_authenticated_user(mock_request)
        
        assert isinstance(result, UserDetails)
        # Falls back to sample user because exact key "x-ms-client-principal-id" not found
        assert result.user_principal_id == sample_user["x-ms-client-principal-id"]

    def test_get_authenticated_user_raises_401_for_empty_principal_id(self):
        """Test get_authenticated_user raises 401 when principal ID is empty"""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "x-ms-client-principal-id": "",  # Empty string
            "x-ms-client-principal-name": "empty.user@example.com"
        }
        
        with pytest.raises(HTTPException) as exc_info:
            get_authenticated_user(mock_request)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "User not authenticated"

    def test_get_authenticated_user_raises_401_for_none_principal_id(self):
        """Test get_authenticated_user raises 401 when principal ID is None"""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "x-ms-client-principal-id": None,
            "x-ms-client-principal-name": "none.user@example.com"
        }
        
        with pytest.raises(HTTPException) as exc_info:
            get_authenticated_user(mock_request)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "User not authenticated"

    @patch('app.libs.services.auth.logger')
    def test_get_authenticated_user_logs_user_principal_id(self, mock_logger):
        """Test get_authenticated_user logs the user principal ID"""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "x-ms-client-principal-id": "logging-test-user-id"
        }
        
        result = get_authenticated_user(mock_request)
        
        assert isinstance(result, UserDetails)
        mock_logger.info.assert_any_call("User object princial id: logging-test-user-id")

    def test_get_authenticated_user_with_empty_headers_dict(self):
        """Test get_authenticated_user with completely empty headers"""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        
        # Should fall back to sample user
        result = get_authenticated_user(mock_request)
        
        assert isinstance(result, UserDetails)
        assert result.user_principal_id == sample_user["x-ms-client-principal-id"]

    def test_get_authenticated_user_header_normalization(self):
        """Test header normalization with proper key present"""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "x-ms-client-principal-id": "UPPERCASE-USER-ID",  # Correct lowercase key
            "X-Ms-Client-Principal-Name": "CamelCase.User@Example.Com"
        }
        
        result = get_authenticated_user(mock_request)
        
        assert isinstance(result, UserDetails)
        assert result.user_principal_id == "UPPERCASE-USER-ID"

    def test_sample_user_constant_values(self):
        """Test that sample_user constant has expected values"""
        assert sample_user["x-ms-client-principal-id"] == "00000000-0000-0000-0000-000000000000"
        assert sample_user["x-ms-client-principal-name"] == "dev.user@example.com"
        assert sample_user["x-ms-client-principal-idp"] == "aad"
        assert sample_user["x-ms-token-aad-id-token"] == "dev.token"
        assert sample_user["x-ms-client-principal"] == "your_base_64_encoded_token"


class TestIntegrationScenarios:
    """Integration test cases covering end-to-end scenarios"""
    
    @patch('app.libs.services.auth.get_tenant_id')
    def test_full_user_authentication_flow_with_tenant(self, mock_get_tenant_id):
        """Test complete authentication flow with tenant ID extraction"""
        mock_get_tenant_id.return_value = "integration-tenant-id"
        
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "x-ms-client-principal-id": "integration-user-id",
            "x-ms-client-principal-name": "integration.user@example.com",
            "x-ms-client-principal-idp": "aad",
            "x-ms-token-aad-id-token": "integration-token",
            "x-ms-client-principal": "integration_base64_token"
        }
        
        # The get_authenticated_user doesn't actually extract tenant from headers,
        # but let's test the UserDetails initialization part
        user_data = {
            "user_principal_id": "integration-user-id",
            "user_name": "integration.user@example.com", 
            "auth_provider": "aad",
            "auth_token": "integration-token",
            "client_principal_b64": "integration_base64_token"
        }
        
        user_details = UserDetails(user_data)
        
        assert user_details.user_principal_id == "integration-user-id"
        assert user_details.user_name == "integration.user@example.com"
        assert user_details.auth_provider == "aad"
        assert user_details.auth_token == "integration-token"
        assert user_details.tenant_id == "integration-tenant-id"
        mock_get_tenant_id.assert_called_once_with("integration_base64_token")

    def test_development_mode_authentication_flow(self):
        """Test authentication flow in development mode (no headers)"""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"user-agent": "test-client"}
        
        result = get_authenticated_user(mock_request)
        
        assert isinstance(result, UserDetails)
        assert result.user_principal_id == sample_user["x-ms-client-principal-id"]
        # In the current implementation, other fields aren't extracted from sample_user
        assert result.user_name is None
        assert result.auth_provider is None
        assert result.auth_token is None
        assert result.tenant_id is None

    def test_authentication_error_scenarios(self):
        """Test various authentication error scenarios"""
        test_cases = [
            {},  # Empty headers
            {"x-ms-client-principal-id": ""},  # Empty principal ID
            {"x-ms-client-principal-id": None},  # None principal ID
            {"other-header": "value"},  # No auth headers
        ]
        
        for headers in test_cases:
            mock_request = Mock(spec=Request)
            if "x-ms-client-principal-id" in headers and (
                headers["x-ms-client-principal-id"] == "" or 
                headers["x-ms-client-principal-id"] is None
            ):
                mock_request.headers = headers
                with pytest.raises(HTTPException) as exc_info:
                    get_authenticated_user(mock_request)
                assert exc_info.value.status_code == 401
            else:
                mock_request.headers = headers
                # Should fall back to sample user and succeed
                result = get_authenticated_user(mock_request)
                assert isinstance(result, UserDetails)
                assert result.user_principal_id == sample_user["x-ms-client-principal-id"]


class TestErrorHandlingAndEdgeCases:
    """Test cases for error handling and edge cases"""
    
    def test_user_details_with_malformed_data_types(self):
        """Test UserDetails initialization with unexpected data types"""
        user_data = {
            "user_principal_id": 12345,  # Number instead of string
            "user_name": ["not", "a", "string"],  # List instead of string
            "auth_provider": {"key": "value"},  # Dict instead of string
            "auth_token": True,  # Boolean instead of string
        }
        
        user_details = UserDetails(user_data)
        
        # UserDetails should accept whatever is provided
        assert user_details.user_principal_id == 12345
        assert user_details.user_name == ["not", "a", "string"]
        assert user_details.auth_provider == {"key": "value"}
        assert user_details.auth_token is True
        assert user_details.tenant_id is None

    def test_get_tenant_id_with_unicode_characters(self):
        """Test get_tenant_id with Unicode characters"""
        user_info = {"tid": "tenant-with-üñíçødé", "sub": "test"}
        json_string = json.dumps(user_info, ensure_ascii=False)
        base64_string = base64.b64encode(json_string.encode('utf-8')).decode('utf-8')
        
        result = get_tenant_id(base64_string)
        
        assert result == "tenant-with-üñíçødé"

    def test_get_tenant_id_with_very_large_json(self):
        """Test get_tenant_id with large JSON payload"""
        user_info = {
            "tid": "large-payload-tenant-id",
            "large_field": "x" * 10000,  # Large string
            "nested": {
                "deep": {
                    "data": ["item"] * 1000  # Large nested structure
                }
            }
        }
        json_string = json.dumps(user_info)
        base64_string = base64.b64encode(json_string.encode('utf-8')).decode('utf-8')
        
        result = get_tenant_id(base64_string)
        
        assert result == "large-payload-tenant-id"

    @patch('app.libs.services.auth.base64.b64decode')
    def test_get_tenant_id_base64_decode_exception(self, mock_b64decode):
        """Test get_tenant_id when base64 decode raises exception"""
        mock_b64decode.side_effect = Exception("Base64 decode error")
        
        result = get_tenant_id("any_string")
        
        assert result == ""

    @patch('app.libs.services.auth.json.loads')
    def test_get_tenant_id_json_loads_exception(self, mock_json_loads):
        """Test get_tenant_id when JSON parsing raises exception"""
        mock_json_loads.side_effect = json.JSONDecodeError("JSON error", "doc", 0)
        
        # Use valid base64 that will decode but fail JSON parsing
        valid_base64 = base64.b64encode(b"not json").decode('utf-8')
        result = get_tenant_id(valid_base64)
        
        assert result == ""

    def test_request_headers_as_dict_behavior(self):
        """Test behavior with different types of header objects"""
        # Test with regular dict
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "x-ms-client-principal-id": "dict-user-id"
        }
        
        result = get_authenticated_user(mock_request)
        assert result.user_principal_id == "dict-user-id"
        
        # Test with case-insensitive dict-like object
        class CaseInsensitiveDict(dict):
            def __getitem__(self, key):
                for k, v in self.items():
                    if k.lower() == key.lower():
                        return v
                raise KeyError(key)
        
        mock_request.headers = CaseInsensitiveDict({
            "x-ms-client-principal-id": "case-insensitive-user-id"  # Use exact lowercase key
        })
        
        result = get_authenticated_user(mock_request)
        assert result.user_principal_id == "case-insensitive-user-id"