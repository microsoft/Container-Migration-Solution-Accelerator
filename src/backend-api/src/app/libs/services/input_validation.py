from uuid import UUID


def is_valid_uuid(value: str) -> bool:
    """Validate if a given string is a valid UUID."""
    try:
        UUID(value, version=4)
        return True
    except ValueError:
        return False
