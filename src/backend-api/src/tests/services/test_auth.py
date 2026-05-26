import base64
import json
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from libs.services.auth import (
    UserDetails,
    get_authenticated_user,
    get_tenant_id,
    sample_user,
)


def _make_request(headers: dict):
    request = MagicMock()
    request.headers = headers
    return request


class TestUserDetails:
    def test_basic_fields_assigned(self):
        details = UserDetails(
            {
                "user_principal_id": "pid-1",
                "user_name": "alice@example.com",
                "auth_provider": "aad",
                "auth_token": "tok",
            }
        )
        assert details.user_principal_id == "pid-1"
        assert details.user_name == "alice@example.com"
        assert details.auth_provider == "aad"
        assert details.auth_token == "tok"
        assert details.tenant_id is None

    def test_missing_keys_default_to_none(self):
        details = UserDetails({})
        assert details.user_principal_id is None
        assert details.user_name is None
        assert details.auth_provider is None
        assert details.auth_token is None
        assert details.tenant_id is None

    def test_tenant_id_extracted_from_client_principal(self):
        principal = {"tid": "tenant-xyz", "oid": "obj"}
        encoded = base64.b64encode(json.dumps(principal).encode()).decode()
        details = UserDetails(
            {"user_principal_id": "pid", "client_principal_b64": encoded}
        )
        assert details.tenant_id == "tenant-xyz"

    def test_placeholder_principal_value_does_not_decode(self):
        details = UserDetails(
            {
                "user_principal_id": "pid",
                "client_principal_b64": "your_base_64_encoded_token",
            }
        )
        assert details.tenant_id is None

    def test_invalid_client_principal_returns_empty_tenant(self):
        details = UserDetails(
            {"user_principal_id": "pid", "client_principal_b64": "@@@not-base64@@@"}
        )
        assert details.tenant_id == ""


class TestGetTenantId:
    def test_returns_tid_when_present(self):
        principal = {"tid": "abc-123"}
        encoded = base64.b64encode(json.dumps(principal).encode()).decode()
        assert get_tenant_id(encoded) == "abc-123"

    def test_returns_empty_string_when_tid_missing(self):
        encoded = base64.b64encode(json.dumps({}).encode()).decode()
        assert get_tenant_id(encoded) == ""

    def test_returns_empty_string_on_decode_failure(self):
        assert get_tenant_id("not-valid-base64-!!!") == ""

    def test_returns_empty_string_on_non_json_payload(self):
        encoded = base64.b64encode(b"not-json-content").decode()
        assert get_tenant_id(encoded) == ""


class TestGetAuthenticatedUser:
    def test_uses_sample_user_when_no_principal_header(self):
        request = _make_request({"some-other-header": "value"})
        user = get_authenticated_user(request)
        assert (
            user.user_principal_id
            == sample_user["x-ms-client-principal-id"]
        )

    def test_uses_request_headers_when_principal_present(self):
        request = _make_request(
            {
                "x-ms-client-principal-id": "real-user-id",
                "x-ms-client-principal-name": "real@example.com",
            }
        )
        user = get_authenticated_user(request)
        assert user.user_principal_id == "real-user-id"

    def test_raises_401_when_principal_id_empty(self):
        request = _make_request({"x-ms-client-principal-id": ""})
        with pytest.raises(HTTPException) as exc_info:
            get_authenticated_user(request)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "User not authenticated"
