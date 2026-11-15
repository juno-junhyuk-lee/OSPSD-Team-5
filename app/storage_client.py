"""DocumentStorage operations over the shared HTTP API."""

from datetime import datetime

import httpx
from cloud_storage_api import (
    DocumentStorage,
    FileInfo,
    InvalidOperationError,
    InvalidRequestError,
    ProviderError,
    ProviderUnavailableError,
    StorageError,
)
from pydantic import BaseModel, ConfigDict

from app.storage_http import StorageHttpTransport


def storage_path(path: str, *, root: bool = False) -> str:
    """Add an optional leading slash; reject ambiguous path segments."""
    if "\\" in path or any(ord(c) < 32 or ord(c) == 127 for c in path):
        raise InvalidRequestError("Invalid storage path.")
    value = path if path.startswith("/") else "/" + path
    if value == "/" and root:
        return value
    if value == "/" or any(part in {"", ".", ".."} for part in value[1:].split("/")):
        raise InvalidRequestError("Invalid storage path.")
    return value


class _FileResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str | None
    name: str
    path: str
    size: int | None
    modified_at: str | None
    etag: str | None
    type: str | None = None

    def to_info(self) -> FileInfo:
        if (
            storage_path(self.path) != self.path
            or self.name != self.path.rsplit("/", 1)[1]
            or (self.id is not None and not self.id)
            or (self.size is not None and self.size < 0)
            or self.type not in {None, "file", "folder"}
        ):
            raise ValueError
        if self.modified_at is not None:
            if not self.modified_at.endswith("Z"):
                raise ValueError
            datetime.fromisoformat(self.modified_at)
        return FileInfo(**self.model_dump())


class HttpDocumentStorage(DocumentStorage):
    """Implement the tagged interface without provider-specific SDK types.

    ProviderError/ProviderUnavailableError after a write may mean it applied.
    This adapter never retries or substitutes another write operation.
    """

    def __init__(self, client: httpx.Client) -> None:
        self._http = StorageHttpTransport(client)

    @staticmethod
    def _metadata(response: httpx.Response, path: str) -> FileInfo:
        try:
            info = _FileResponse.model_validate(response.json()).to_info()
            # Dropbox can return the canonical letter case of an existing folder.
            if info.path.casefold() != path.casefold():
                raise ValueError
            return info
        except ValueError, InvalidRequestError:
            raise ProviderError("Storage returned invalid metadata.") from None

    def _upload(self, method: str, path: str, content: bytes) -> FileInfo:
        path = storage_path(path)
        response = self._http.request(
            method,
            "files",
            expected=201 if method == "POST" else 200,
            data={"path": path},
            files={
                "file": (path.rsplit("/", 1)[1], content, "application/octet-stream")
            },
        )
        info = self._metadata(response, path)
        if info.size != len(content) or info.type == "folder":
            raise ProviderError("Storage returned invalid upload metadata.")
        return info

    def create(self, path: str, content: bytes) -> FileInfo:
        return self._upload("POST", path, content)

    def replace(self, path: str, content: bytes) -> FileInfo:
        return self._upload("PUT", path, content)

    def download(self, path: str) -> bytes:
        return self._http.request(
            "GET", "files/download", expected=200, params={"path": storage_path(path)}
        ).content

    def get_metadata(self, path: str) -> FileInfo:
        path = storage_path(path)
        response = self._http.request(
            "GET", "files/metadata", expected=200, params={"path": path}
        )
        return self._metadata(response, path)

    def list_files(self, path: str) -> list[FileInfo]:
        path = storage_path(path, root=True)
        response = self._http.request(
            "GET", "files", expected=200, params={"path": path}
        )
        try:
            payload = response.json()
            if not isinstance(payload, list):
                raise ValueError
            entries = [_FileResponse.model_validate(item).to_info() for item in payload]
            if any(
                item.type not in {"file", "folder"}
                or item.path.rsplit("/", 1)[0].casefold() != path.rstrip("/").casefold()
                for item in entries
            ) or len({item.path for item in entries}) != len(entries):
                raise ValueError
            return sorted(entries, key=lambda item: item.path)
        except ValueError, InvalidRequestError:
            raise ProviderError("Storage returned an invalid folder listing.") from None

    def move(self, from_path: str, to_path: str) -> FileInfo:
        source, target = storage_path(from_path), storage_path(to_path)
        response = self._http.request(
            "PATCH",
            "files",
            expected=200,
            params={"path": source},
            body={"new_path": target},
        )
        return self._metadata(response, target)

    def delete(self, path: str) -> None:
        if path in {"", "/"}:
            raise InvalidOperationError("The storage root cannot be deleted.")
        response = self._http.request(
            "DELETE", "files", expected=204, params={"path": storage_path(path)}
        )
        if response.content:
            raise ProviderError("Storage returned an invalid deletion response.")

    def check_health(self) -> None:
        try:
            response = self._http.request("GET", "health/provider", expected=200)
            if response.json() != {"status": "ok"}:
                raise ValueError
        except StorageError, ValueError:
            raise ProviderUnavailableError("Storage health check failed.") from None
