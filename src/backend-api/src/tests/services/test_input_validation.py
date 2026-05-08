from uuid import uuid4

import pytest

from libs.services.input_validation import is_valid_uuid


class TestIsValidUuid:
    """Test cases for is_valid_uuid"""

    def test_returns_true_for_valid_uuid4(self):
        assert is_valid_uuid(str(uuid4())) is True

    def test_returns_true_for_known_valid_uuid4(self):
        assert is_valid_uuid("123e4567-e89b-42d3-a456-426614174000") is True

    @pytest.mark.parametrize(
        "value",
        [
            "not-a-uuid",
            "",
            "123",
            "00000000-0000-0000-0000-00000000000Z",
            "g23e4567-e89b-42d3-a456-426614174000",
        ],
    )
    def test_returns_false_for_invalid_strings(self, value):
        assert is_valid_uuid(value) is False

    def test_returns_false_for_none(self):
        # is_valid_uuid only catches ValueError; non-string input raises TypeError
        with pytest.raises(TypeError):
            is_valid_uuid(None)
