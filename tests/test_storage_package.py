"""Offline package construction, secret boundaries and client lifetime checks."""

import json
import os
import socket
from pathlib import Path
from unittest.mock import patch

import pytest
from cloud_storage_api import ProviderError

from app.storage_package import PackageStorageSettings, package_summary_store
from app.summary_storage import SummaryStorageError


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in tuple(os.environ):
        if name.startswith("DROPBOX_") or name.startswith("STORAGE_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("STORAGE_ROOT_PATH", "/hw3-tests")
    monkeypatch.setenv("DROPBOX_APP_KEY", "test-key")
    monkeypatch.setenv("DROPBOX_APP_SECRET", "test-secret")
    monkeypatch.setenv("DROPBOX_REFRESH_TOKEN", "test-refresh")

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("Package construction must not contact the provider")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


def assert_configuration_failure() -> None:
    with pytest.raises(SummaryStorageError) as caught:
        with package_summary_store():
            pytest.fail("Invalid configuration must not yield a store")
    error = caught.value
    assert str(error) == "The summary storage is not configured or unavailable."
    assert not error.configured
    assert not error.may_have_applied
    assert not error.retryable
    assert error.path is None
    assert error.__suppress_context__


@pytest.mark.parametrize(
    "name,value",
    [
        ("PYTHON_DOTENV_DISABLED", "0"),
        ("STORAGE_ROOT_PATH", "/"),
        ("STORAGE_ROOT_PATH", "/../secret"),
        ("DROPBOX_APP_KEY", ""),
        ("DROPBOX_APP_SECRET", "  "),
        ("DROPBOX_REFRESH_TOKEN", ""),
    ],
)
def test_invalid_settings_stop_before_package_construction(
    name: str, value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(name, value)
    with patch("app.storage_package._create_storage") as create:
        assert_configuration_failure()
    create.assert_not_called()


def test_refresh_environment_precedes_file_and_repr_hides_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DROPBOX_TOKEN_FILE", "relative-must-not-be-read.json")
    settings = PackageStorageSettings.from_environment()
    assert settings.refresh_token == "test-refresh"
    for secret in ("test-key", "test-secret", "test-refresh"):
        assert secret not in repr(settings)


def test_explicit_absolute_token_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "token.json"
    token_file.write_text(json.dumps({"refresh_token": "file-refresh"}))
    monkeypatch.delenv("DROPBOX_REFRESH_TOKEN")
    monkeypatch.setenv("DROPBOX_TOKEN_FILE", str(token_file))
    assert PackageStorageSettings.from_environment().refresh_token == "file-refresh"


@pytest.mark.parametrize(
    "payload", ["{broken", "[]", "{}", '{"refresh_token":7}', '{"refresh_token":" "}']
)
def test_invalid_token_file_is_sanitized(
    payload: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "secret-token.json"
    token_file.write_text(payload)
    monkeypatch.delenv("DROPBOX_REFRESH_TOKEN")
    monkeypatch.setenv("DROPBOX_TOKEN_FILE", str(token_file))
    assert_configuration_failure()


@pytest.mark.parametrize("path", ["relative.json", "missing", "directory"])
def test_unusable_file_path(
    path: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DROPBOX_REFRESH_TOKEN")
    value = path if path == "relative.json" else str(tmp_path / path)
    if path == "directory":
        Path(value).mkdir()
    monkeypatch.setenv("DROPBOX_TOKEN_FILE", value)
    assert_configuration_failure()


def test_real_package_construction_disables_retries_and_closes_sdk() -> None:
    with patch("dropbox.Dropbox") as sdk_type:
        sdk = sdk_type.return_value
        with package_summary_store() as store:
            assert store is not None
            sdk.close.assert_not_called()
        sdk_type.assert_called_once_with(
            oauth2_refresh_token="test-refresh",
            app_key="test-key",
            app_secret="test-secret",
            timeout=30,
            max_retries_on_error=0,
            max_retries_on_rate_limit=0,
        )
        sdk.close.assert_called_once_with()


def test_real_sdk_and_package_construct_without_network() -> None:
    with package_summary_store() as store:
        assert store is not None


def test_sdk_construction_failure_is_sanitized() -> None:
    with patch("dropbox.Dropbox", side_effect=ValueError("test-secret")):
        assert_configuration_failure()


def test_wrapper_construction_failure_closes_sdk() -> None:
    with (
        patch("dropbox.Dropbox") as sdk_type,
        patch(
            "dropbox_client_impl.DropboxDocumentStorage",
            side_effect=RuntimeError("test-secret"),
        ),
    ):
        assert_configuration_failure()
        sdk_type.return_value.close.assert_called_once_with()


def test_operation_error_is_not_reclassified_as_configuration_failure() -> None:
    failure = ProviderError("controlled operation failure")
    with patch("dropbox.Dropbox") as sdk_type:
        with pytest.raises(ProviderError) as caught:
            with package_summary_store():
                raise failure
        assert caught.value is failure
        sdk_type.return_value.close.assert_called_once_with()
