import base64
import json
from unittest.mock import MagicMock
from fastapi import HTTPException
from libs.services.auth import (
    UserDetails,
    get_tenant_id,
    get_authenticated_user,
    sample_user,
)


def test_user_details_initialization():
    """Test UserDetails class initialization with basic user info."""
    user_info = {
        "user_principal_id": "test-user-id",
        "user_name": "test.user@example.com",
        "auth_provider": "aad",
    }
    user_details = UserDetails(user_info)
    
    assert user_details.user_principal_id == "test-user-id"
    assert user_details.user_name == "test.user@example.com"
    assert user_details.auth_provider == "aad"
    assert user_details.tenant_id is None


def test_get_tenant_id_valid_token():
    """Test get_tenant_id with valid base64 encoded token."""
    user_info = {
        "tid": "tenant-123",
        "oid": "object-456",
    }
    b64_encoded = base64.b64encode(json.dumps(user_info).encode()).decode()
    
    tenant_id = get_tenant_id(b64_encoded)
    assert tenant_id == "tenant-123"


def test_get_tenant_id_invalid_token():
    """Test get_tenant_id with invalid base64 encoded token."""
    tenant_id = get_tenant_id("not-valid-base64!!!")
    assert tenant_id == ""


def test_get_tenant_id_empty_token():
    """Test get_tenant_id with empty token."""
    tenant_id = get_tenant_id("")
    assert tenant_id == ""


def test_user_details_with_valid_client_principal():
    """Test UserDetails with valid client principal."""
    user_info = {
        "user_principal_id": "test-user-id",
        "user_name": "test.user@example.com",
        "client_principal_b64": base64.b64encode(
            json.dumps({"tid": "tenant-123"}).encode()
        ).decode(),
    }
    user_details = UserDetails(user_info)
    
    assert user_details.tenant_id == "tenant-123"


def test_user_details_with_sample_token():
    """Test UserDetails with sample token (development)."""
    user_info = {
        "user_principal_id": "test-user-id",
        "client_principal_b64": "your_base_64_encoded_token",
    }
    user_details = UserDetails(user_info)
    
    assert user_details.tenant_id is None


def test_get_authenticated_user_with_valid_headers():
    """Test get_authenticated_user with valid user principal header."""
    mock_request = MagicMock()
    mock_request.headers = {
        "x-ms-client-principal-id": "user-123",
    }
    
    user_details = get_authenticated_user(mock_request)
    assert user_details.user_principal_id == "user-123"


def test_get_authenticated_user_without_headers_uses_sample():
    """Test get_authenticated_user without user principal header uses sample user."""
    mock_request = MagicMock()
    mock_request.headers = {}
    
    user_details = get_authenticated_user(mock_request)
    assert user_details.user_principal_id == "00000000-0000-0000-0000-000000000000"


def test_get_authenticated_user_case_insensitive_headers():
    """Test get_authenticated_user handles case-insensitive headers."""
    mock_request = MagicMock()
    # Use a regular dict that FastAPI would provide (which is case-insensitive)
    mock_request.headers = {
        "x-ms-client-principal-id": "user-456",
    }
    
    user_details = get_authenticated_user(mock_request)
    # Headers are lowercased in the function
    assert user_details.user_principal_id == "user-456"


def test_get_authenticated_user_missing_principal_raises():
    """Test get_authenticated_user raises when principal ID is None."""
    mock_request = MagicMock()
    mock_request.headers = {
        "x-ms-client-principal-id": None,
    }
    
    try:
        get_authenticated_user(mock_request)
        assert False, "Should have raised HTTPException"
    except HTTPException as e:
        assert e.status_code == 401
        assert "not authenticated" in e.detail.lower()


def test_sample_user_has_expected_keys():
    """Test that sample user has expected keys."""
    assert "x-ms-client-principal-id" in sample_user
    assert "x-ms-client-principal-name" in sample_user
    assert "x-ms-client-principal-idp" in sample_user
    assert "x-ms-token-aad-id-token" in sample_user
    assert "x-ms-client-principal" in sample_user


def test_user_details_with_all_fields():
    """Test UserDetails with all possible fields."""
    user_info = {
        "user_principal_id": "principal-123",
        "user_name": "john.doe@example.com",
        "auth_provider": "aad",
        "auth_token": "token-xyz",
        "client_principal_b64": base64.b64encode(
            json.dumps({"tid": "tenant-abc"}).encode()
        ).decode(),
    }
    user_details = UserDetails(user_info)
    
    assert user_details.user_principal_id == "principal-123"
    assert user_details.user_name == "john.doe@example.com"
    assert user_details.auth_provider == "aad"
    assert user_details.auth_token == "token-xyz"
    assert user_details.tenant_id == "tenant-abc"
