"""Construct package-backed summary storage before any workflow writes.

Only explicit environment configuration and an absolute token-file path are
used. Importing this module does not import Team 3 or load dotenv/credentials.
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

from app.storage_client import storage_path
from app.summary_storage import DocumentSummaryStore, SummaryStorageError


class _Closeable(Protocol):
    def close(self) -> None: ...


class _PackageSummaryStore(DocumentSummaryStore):
    def _creation_may_have_applied(self, error: StorageError) -> bool:
        if not super()._creation_may_have_applied(error):
            return False
        # The pinned Team 3 code preserves SDK -> builtin -> shared causes.
        # Only typed connection-establishment evidence proves no request was sent.
        from requests.exceptions import (
            ConnectionError as RequestsConnectionError,
        )
        from requests.exceptions import (
            ConnectTimeout,
        )
        from urllib3.exceptions import MaxRetryError, NewConnectionError

        cause = error.__cause__
        if (
            isinstance(error, ProviderUnavailableError)
            and type(cause) is ConnectionError
        ):
            sdk_error = cause.__cause__
            if isinstance(sdk_error, ConnectTimeout):
                return False
            if isinstance(sdk_error, RequestsConnectionError) and sdk_error.args:
                pool_error = sdk_error.args[0]
                if isinstance(pool_error, MaxRetryError) and isinstance(
                    pool_error.reason, NewConnectionError
                ):
                    return False
        return True


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

    @classmethod
    def from_environment(cls) -> "PackageStorageSettings":
        try:
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
        return cls(root, key, secret, token)


def _create_storage(
    settings: PackageStorageSettings,
) -> tuple[DocumentStorage, _Closeable]:
    # Lazy imports keep application import independent of package auth setup.
    import dropbox  # type: ignore[import-untyped]
    from dropbox_client_impl import DropboxClient, DropboxDocumentStorage

    sdk = dropbox.Dropbox(
        oauth2_refresh_token=settings.refresh_token,
        app_key=settings.app_key,
        app_secret=settings.app_secret,
        timeout=30,
        max_retries_on_error=0,
        max_retries_on_rate_limit=0,
    )
    try:
        storage = DropboxDocumentStorage(client=DropboxClient(dbx=sdk))
    except Exception:
        sdk.close()
        raise
    return storage, sdk


@contextmanager
def package_summary_store() -> Iterator[DocumentSummaryStore]:
    """Own the SDK lifetime; only construction errors are configuration failures.

    Token validity is checked by Dropbox on first use, not during construction.
    Operation/body errors retain their original certainty and are not remapped.
    """
    settings = PackageStorageSettings.from_environment()
    try:
        storage, sdk = _create_storage(settings)
    except Exception:
        raise _configuration_error() from None
    try:
        yield _PackageSummaryStore(storage, settings.root_path)
    finally:
        sdk.close()
