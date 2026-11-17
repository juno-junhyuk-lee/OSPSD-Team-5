"""Provider-independent validation for paths below the storage root."""

from cloud_storage_api import InvalidRequestError


def storage_path(path: str) -> str:
    """Add an optional leading slash; reject root and ambiguous path segments."""
    if "\\" in path or any(ord(c) < 32 or ord(c) == 127 for c in path):
        raise InvalidRequestError("Invalid storage path.")
    value = path if path.startswith("/") else "/" + path
    if value == "/" or any(part in {"", ".", ".."} for part in value[1:].split("/")):
        raise InvalidRequestError("Invalid storage path.")
    return value
