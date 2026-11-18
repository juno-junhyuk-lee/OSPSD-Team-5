"""Construct package-backed summary storage before any workflow writes.

Only explicit environment configuration and an absolute token-file path are
used. Importing this module does not import providers or load dotenv/credentials.
"""

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from cloud_storage_api import (
    DocumentStorage,
    InvalidRequestError,
    ProviderUnavailableError,
    StorageError,
)

from app.storage_paths import storage_path
from app.summary_storage import DocumentSummaryStore, SummaryStorageError


class _Closeable(Protocol):
    def close(self) -> None: ...


def _connection_was_not_established(error: BaseException | None) -> bool:
    """Use typed Requests/urllib3 evidence, never provider exception messages."""
    from requests.exceptions import ConnectionError as RequestsConnectionError
    from requests.exceptions import ConnectTimeout
    from urllib3.exceptions import MaxRetryError, NewConnectionError

    if isinstance(error, ConnectTimeout):
        return True
    if isinstance(error, RequestsConnectionError) and error.args:
        pool_error = error.args[0]
        return isinstance(pool_error, MaxRetryError) and isinstance(
            pool_error.reason, NewConnectionError
        )
    return False


class _PackageSummaryStore(DocumentSummaryStore):
    def _creation_may_have_applied(self, error: StorageError) -> bool:
        if not super()._creation_may_have_applied(error):
            return False
        # The pinned Team 3 code preserves SDK -> builtin -> shared causes.
        cause = error.__cause__
        if (
            isinstance(error, ProviderUnavailableError)
            and type(cause) is ConnectionError
        ):
            return not _connection_was_not_established(cause.__cause__)
        return True


class _Team1SummaryStore(DocumentSummaryStore):
    def _creation_may_have_applied(self, error: StorageError) -> bool:
        if not super()._creation_may_have_applied(error):
            return False
        # Team 1 784be97 preserves the SDK exception directly as the shared cause.
        return not (
            isinstance(error, ProviderUnavailableError)
            and _connection_was_not_established(error.__cause__)
        )


def _configuration_error() -> SummaryStorageError:
    return SummaryStorageError(
        "The summary storage is not configured or unavailable.",
        may_have_applied=False,
        configured=False,
        retryable=False,
    )


@dataclass(frozen=True)
class PackageStorageSettings:
    root_path: str
    app_key: str = field(repr=False)
    app_secret: str = field(repr=False)
    refresh_token: str = field(repr=False)
    implementation: str = "team3_dropbox"

    @classmethod
    def from_environment(cls) -> "PackageStorageSettings":
        try:
            implementation = os.environ.get("STORAGE_IMPLEMENTATION", "team3_dropbox")
            if implementation not in {"team3_dropbox", "team1_dropbox"}:
                raise ValueError
            # Team 3 calls load_dotenv on import. Require its explicit opt-out.
            if os.environ.get("PYTHON_DOTENV_DISABLED") != "1":
                raise ValueError
            root = storage_path(os.environ["STORAGE_ROOT_PATH"])
            key = os.environ["DROPBOX_APP_KEY"].strip()
            secret = os.environ["DROPBOX_APP_SECRET"].strip()
            token = os.environ.get("DROPBOX_REFRESH_TOKEN", "").strip()
            if not token:
                token_path = Path(os.environ["DROPBOX_TOKEN_FILE"])
                if not token_path.is_absolute():
                    raise ValueError
                payload = json.loads(token_path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError
                file_token = payload.get("refresh_token")
                if not isinstance(file_token, str):
                    raise ValueError
                token = file_token.strip()
            if not key or not secret or not token:
                raise ValueError
        except KeyError, ValueError, OSError, InvalidRequestError:
            raise _configuration_error() from None
        return cls(root, key, secret, token, implementation)


def _create_storage(
    settings: PackageStorageSettings,
) -> tuple[DocumentStorage, _Closeable]:
    # Lazy imports keep application import independent of package auth setup.
    if settings.implementation not in {"team3_dropbox", "team1_dropbox"}:
        raise _configuration_error()
    import dropbox  # type: ignore[import-untyped]

    sdk = dropbox.Dropbox(
        oauth2_refresh_token=settings.refresh_token,
        app_key=settings.app_key,
        app_secret=settings.app_secret,
        timeout=30,
        max_retries_on_error=0,
        max_retries_on_rate_limit=0,
    )
    try:
        storage: DocumentStorage
        if settings.implementation == "team1_dropbox":
            from team1_dropbox import Team1DropboxStorage

            storage = Team1DropboxStorage(client=sdk)
        else:
            from dropbox_client_impl import DropboxClient, DropboxDocumentStorage

            storage = DropboxDocumentStorage(client=DropboxClient(dbx=sdk))
    except Exception:
        sdk.close()
        raise
    return storage, sdk


@contextmanager
def package_document_storage(
    settings: PackageStorageSettings,
) -> Iterator[DocumentStorage]:
    """Share scoped SDK construction between the workflow and opt-in live probe."""
    try:
        storage, sdk = _create_storage(settings)
    except Exception:
        raise _configuration_error() from None
    try:
        yield storage
    finally:
        sdk.close()


@contextmanager
def package_summary_store() -> Iterator[DocumentSummaryStore]:
    """Read explicit configuration; preserve operation errors after construction."""
    settings = PackageStorageSettings.from_environment()
    with package_document_storage(settings) as storage:
        if settings.implementation == "team3_dropbox":
            yield _PackageSummaryStore(storage, settings.root_path)
        else:
            yield _Team1SummaryStore(storage, settings.root_path)
