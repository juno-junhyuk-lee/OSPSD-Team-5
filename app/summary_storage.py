"""Storage boundary for workflow Markdown summaries.

The workflow supplies Markdown; DocumentSummaryStore saves and verifies UTF-8
bytes through the shared contract. Controlled stores can still be substituted.
"""

from typing import Protocol

from cloud_storage_api import (
    ConflictError,
    DocumentStorage,
    FileTooLargeError,
    InvalidOperationError,
    InvalidRequestError,
    NotFoundError,
    PermissionDeniedError,
    StorageError,
)
from pydantic import BaseModel

from app.storage_paths import storage_path


class StoredSummary(BaseModel):
    """Where a saved summary can be found; the ID is opaque to the workflow."""

    id: str


class SummaryStorageError(Exception):
    """A sanitized storage failure; adapters must not include provider details.

    may_have_applied = the summary might have been saved despite the failure.
    """

    def __init__(
        self,
        message: str,
        *,
        may_have_applied: bool,
        retryable: bool = False,
        configured: bool = True,
        path: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.may_have_applied = may_have_applied
        self.retryable = retryable
        self.configured = configured
        # Caller-visible storage path, supplied locally rather than remote error text.
        self.path = path


class SummaryStore(Protocol):
    def save_summary(self, name: str, markdown: str) -> StoredSummary:
        """Save one Markdown document; raise SummaryStorageError on failure."""
        ...


class DocumentSummaryStore:
    """Create one summary under an isolated root and verify its exact contents."""

    def __init__(self, storage: DocumentStorage, root_path: str) -> None:
        self._storage = storage
        self._root = storage_path(root_path)

    def _creation_may_have_applied(self, error: StorageError) -> bool:
        # Unknown shared errors do not guarantee that a write was rejected.
        return not isinstance(
            error,
            (
                ConflictError,
                FileTooLargeError,
                InvalidOperationError,
                InvalidRequestError,
                NotFoundError,
                PermissionDeniedError,
            ),
        )

    def save_summary(self, name: str, markdown: str) -> StoredSummary:
        if (
            not name
            or name in {".", ".."}
            or "/" in name
            or "\\" in name
            or any(ord(c) < 32 or ord(c) == 127 for c in name)
        ):
            raise SummaryStorageError(
                "Invalid summary filename.", may_have_applied=False
            )
        try:
            content = markdown.encode("utf-8")
        except UnicodeEncodeError:
            raise SummaryStorageError(
                "Invalid summary text.", may_have_applied=False
            ) from None
        path = self._root + "/" + name
        created = False
        try:
            info = self._storage.create(path, content)
            created = True
            if self._storage.download(path) != content:
                raise SummaryStorageError(
                    "Stored summary contents could not be verified.",
                    may_have_applied=True,
                    path=path,
                )
            # Keep metadata access inside the uncertainty boundary too.
            return StoredSummary(id=info.id or info.path)
        except SummaryStorageError:
            raise
        except StorageError as error:
            raise SummaryStorageError(
                "Summary storage request failed.",
                may_have_applied=created or self._creation_may_have_applied(error),
                path=path,
            ) from None
        except Exception:
            # A package defect or untyped failure provides no absence guarantee.
            raise SummaryStorageError(
                "Summary storage request failed.", may_have_applied=True, path=path
            ) from None
