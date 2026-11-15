"""Offline storage connection and error-boundary checks."""

from unittest.mock import patch

import httpx
import pytest
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

from app.storage_http import StorageHttpTransport
from app.storage_settings import (
    StorageConfigurationError,
    StorageSettings,
    storage_http_client,
)


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("STORAGE_BASE_URL", "STORAGE_TIMEOUT_SECONDS", "STORAGE_BEARER_TOKEN"):
        monkeypatch.delenv(key, raising=False)


@pytest.mark.parametrize(
    "url",
    [
        "https://storage.example/api",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://[::1]:8000",
    ],
)
def test_base_url_and_timeout_defaults(
    url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STORAGE_BASE_URL", url)
    settings = StorageSettings.from_environment()
    assert settings.base_url == url + "/"
    assert settings.timeout_seconds == 30
    assert settings.bearer_token is None


@pytest.mark.parametrize(
    "key,value",
    [
        ("STORAGE_BASE_URL", ""),
        ("STORAGE_BASE_URL", "http://remote.example"),
        ("STORAGE_BASE_URL", "https://user:SECRET@storage.example"),
        ("STORAGE_BASE_URL", "https://storage.example?key=SECRET"),
        ("STORAGE_BASE_URL", "https://storage.example#SECRET"),
        ("STORAGE_BASE_URL", "https://storage.example/\nSECRET"),
        ("STORAGE_BASE_URL", "ftp://storage.example"),
        ("STORAGE_BASE_URL", "https://storage.example:0"),
        ("STORAGE_TIMEOUT_SECONDS", "nan"),
        ("STORAGE_TIMEOUT_SECONDS", "inf"),
        ("STORAGE_TIMEOUT_SECONDS", "0"),
        ("STORAGE_TIMEOUT_SECONDS", "121"),
        ("STORAGE_TIMEOUT_SECONDS", "bad"),
        ("STORAGE_BEARER_TOKEN", ""),
        ("STORAGE_BEARER_TOKEN", "SECRET\r\nheader"),
    ],
)
def test_bad_settings_fail_without_exposing_values(
    key: str, value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STORAGE_BASE_URL", "https://storage.example")
    monkeypatch.setenv(key, value)
    with pytest.raises(StorageConfigurationError) as caught:
        StorageSettings.from_environment()
    assert "SECRET" not in str(caught.value)
    assert caught.value.__suppress_context__


def test_missing_url_is_a_local_configuration_error() -> None:
    with pytest.raises(StorageConfigurationError):
        StorageSettings.from_environment()


@pytest.mark.parametrize("fail", [False, True])
def test_client_lifecycle_and_configured_request(
    fail: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STORAGE_BASE_URL", "https://storage.example/api/")
    monkeypatch.setenv("STORAGE_BEARER_TOKEN", "SECRET")
    monkeypatch.setenv("STORAGE_TIMEOUT_SECONDS", "12.5")
    settings = StorageSettings.from_environment()
    assert "SECRET" not in repr(settings)

    def respond(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://storage.example/api/files"
        assert request.headers["Authorization"] == "Bearer SECRET"
        assert request.extensions["timeout"]["read"] == 12.5
        return httpx.Response(200, content=b"ok")

    real_client = httpx.Client(
        base_url=settings.base_url,
        timeout=settings.timeout_seconds,
        headers={"Authorization": "Bearer SECRET"},
        transport=httpx.MockTransport(respond),
    )
    with patch("app.storage_settings.httpx.Client", return_value=real_client) as build:
        try:
            with storage_http_client(settings) as client:
                assert (
                    StorageHttpTransport(client)
                    .request("GET", "files", expected=200)
                    .content
                    == b"ok"
                )
                if fail:
                    raise RuntimeError("consumer failed")
        except RuntimeError:
            assert fail
    assert real_client.is_closed
    assert build.call_args.kwargs["follow_redirects"] is False
    assert build.call_args.kwargs["trust_env"] is False


@pytest.mark.parametrize(
    "status,code,error_type",
    [
        (400, "invalid_request", InvalidRequestError),
        (403, "permission_denied", PermissionDeniedError),
        (404, "not_found", NotFoundError),
        (409, "conflict", ConflictError),
        (413, "file_too_large", FileTooLargeError),
        (422, "invalid_operation", InvalidOperationError),
        (502, "provider_error", ProviderError),
        (503, "provider_unavailable", ProviderUnavailableError),
    ],
)
def test_shared_errors_keep_their_type_without_remote_messages(
    status: int,
    code: str,
    error_type: type[StorageError],
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            status, json={"error": {"code": code, "message": "SECRET"}}
        )

    with httpx.Client(
        base_url="https://storage.example/", transport=httpx.MockTransport(respond)
    ) as client:
        with pytest.raises(error_type) as caught:
            StorageHttpTransport(client).request("POST", "files", expected=201)
    assert str(caught.value) == "Storage request failed."
    assert "SECRET" not in caplog.text
    assert calls == 1


@pytest.mark.parametrize(
    "mode",
    [
        "timeout",
        "redirect",
        "wrong_status",
        "invalid_json",
        "wrong_code",
        "list_error",
        "missing_error",
    ],
)
def test_uncertain_responses_are_not_retried_or_reported_as_rejections(
    mode: str,
) -> None:
    calls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if mode == "timeout":
            raise httpx.ReadTimeout("SECRET", request=request)
        if mode == "redirect":
            return httpx.Response(307, headers={"Location": "https://other.example/"})
        if mode == "wrong_status":
            return httpx.Response(200, json={"id": "file"})
        if mode == "invalid_json":
            return httpx.Response(409, content=b"SECRET")
        payload: object = {"error": {"code": "not_found"}}
        if mode == "list_error":
            payload = []
        elif mode == "missing_error":
            payload = {}
        return httpx.Response(409, json=payload)

    with httpx.Client(
        base_url="https://storage.example/",
        follow_redirects=True,
        transport=httpx.MockTransport(respond),
    ) as client:
        with pytest.raises(
            ProviderUnavailableError if mode == "timeout" else ProviderError
        ) as caught:
            StorageHttpTransport(client).request("POST", "files", expected=201)
    assert "SECRET" not in str(caught.value)
    assert calls == ["https://storage.example/files"]
