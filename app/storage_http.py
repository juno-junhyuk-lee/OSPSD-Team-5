"""HTTP transport for shared storage routes; no provider retries or raw errors."""

import httpx
from cloud_storage_api import (
    ConflictError,
    FileTooLargeError,
    InvalidOperationError,
    InvalidRequestError,
    NotFoundError,
    PermissionDeniedError,
    ProviderError,
    ProviderUnavailableError,
    StorageError,
)

_ERRORS: dict[int, type[StorageError]] = {
    400: InvalidRequestError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    413: FileTooLargeError,
    422: InvalidOperationError,
    502: ProviderError,
    503: ProviderUnavailableError,
}


class StorageHttpTransport:
    """Use a caller-owned client. Provider errors never prove a write failed."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def request(
        self,
        method: str,
        route: str,
        *,
        expected: int,
        params: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        body: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Send once, require the operation's status, and translate shared errors.

        A timeout, 5xx, redirect or invalid response may follow an applied write.
        The operation adapter must preserve that uncertainty for its caller.
        """
        try:
            response = self._client.request(
                method,
                route,
                params=params,
                data=data,
                files=files,
                json=body,
                follow_redirects=False,
            )
        except httpx.RequestError:
            raise ProviderUnavailableError(
                "Storage request could not be confirmed."
            ) from None
        if response.status_code == expected:
            return response
        error_type = _ERRORS.get(response.status_code)
        try:
            payload = response.json()
            if error_type is None or payload["error"]["code"] != error_type.code:
                raise ValueError
        except ValueError, KeyError, TypeError:
            raise ProviderError("Storage returned an invalid response.") from None
        assert error_type is not None
        raise error_type("Storage request failed.")
