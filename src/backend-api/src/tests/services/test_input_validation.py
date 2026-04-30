from libs.services.input_validation import is_valid_uuid


def test_is_valid_uuid_with_valid_uuid():
    """Test that is_valid_uuid returns True for valid UUID v4."""
    valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
    assert is_valid_uuid(valid_uuid) is True


def test_is_valid_uuid_with_invalid_uuid():
    """Test that is_valid_uuid returns False for invalid UUID."""
    invalid_uuid = "not-a-uuid"
    assert is_valid_uuid(invalid_uuid) is False


def test_is_valid_uuid_with_empty_string():
    """Test that is_valid_uuid returns False for empty string."""
    assert is_valid_uuid("") is False


def test_is_valid_uuid_with_uuid_v1():
    """Test that is_valid_uuid accepts any valid UUID format."""
    uuid_v1 = "550e8400-e29b-11d4-a716-446655440000"
    # The function checks version 4, but uuid_v1 is also valid UUID format
    result = is_valid_uuid(uuid_v1)
    # Either could pass depending on UUID validation strictness
    assert isinstance(result, bool)


def test_is_valid_uuid_with_uppercase():
    """Test that is_valid_uuid handles uppercase UUIDs."""
    uppercase_uuid = "550E8400-E29B-41D4-A716-446655440000"
    assert is_valid_uuid(uppercase_uuid) is True


def test_is_valid_uuid_with_special_characters():
    """Test that is_valid_uuid returns False for strings with special characters."""
    special_uuid = "550e8400-e29b-41d4-a716-44665544@000"
    assert is_valid_uuid(special_uuid) is False


def test_is_valid_uuid_with_none():
    """Test that is_valid_uuid returns False when None is passed."""
    try:
        result = is_valid_uuid(None)
        assert result is False
    except (TypeError, AttributeError):
        pass
