import json
from json import JSONDecodeError
from unittest.mock import MagicMock

import pytest
from google.auth.exceptions import GoogleAuthError, RefreshError, TransportError
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from httplib2 import HttpLib2Error, Response  # type: ignore[import-untyped]
from requests.exceptions import RequestException

from app.calendar_provider import (
    CalendarMetadataAccessDeniedError,
    CalendarMetadataAuthenticationError,
    CalendarMetadataNotFoundError,
    CalendarMetadataProviderError,
    CalendarMetadataUnavailableError,
    CalendarReader,
)
from app.google_calendar import GoogleCalendarReader


@pytest.fixture
def service(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    sdk = MagicMock()
    sdk.calendars.return_value.get.return_value.execute.return_value = {
        "id": "private-account-id",
        "summary": "Real title",
        "timeZone": "Europe/London",
        "etag": "hidden",
    }
    monkeypatch.setattr(
        "app.google_calendar.Credentials.from_authorized_user_file",
        lambda path: object(),
    )
    build = MagicMock()
    build.return_value.__enter__.return_value = sdk
    monkeypatch.setattr("app.google_calendar.build", build)
    sdk.client_builder = build
    return sdk


def http_error(status: int, reason: str = "forbidden") -> HttpError:
    return HttpError(
        Response({"status": str(status)}),
        json.dumps(
            {"error": {"errors": [{"reason": reason}], "message": "secret"}}
        ).encode(),
    )


def test_provider_metadata_is_translated(service: MagicMock) -> None:
    reader: CalendarReader = GoogleCalendarReader()

    assert reader.get_primary_calendar().model_dump() == {
        "id": "primary",
        "title": "Real title",
        "time_zone": "Europe/London",
    }
    service.calendars.return_value.get.assert_called_once_with(calendarId="primary")
    service.calendars.return_value.get.return_value.execute.assert_called_once_with(
        num_retries=0
    )
    assert_client_closed(service)


def assert_client_closed(service: MagicMock) -> None:
    service.client_builder.return_value.__exit__.assert_called_once()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (http_error(404), CalendarMetadataNotFoundError),
        (http_error(401), CalendarMetadataAuthenticationError),
        (http_error(403), CalendarMetadataAccessDeniedError),
        *[
            (http_error(403, reason), CalendarMetadataUnavailableError)
            for reason in (
                "rateLimitExceeded",
                "userRateLimitExceeded",
                "quotaExceeded",
            )
        ],
        *[
            (http_error(status), CalendarMetadataUnavailableError)
            for status in (408, 429, 500, 502, 503, 504)
        ],
        (http_error(400), CalendarMetadataProviderError),
        (JSONDecodeError("Invalid JSON", "", 0), CalendarMetadataProviderError),
        (RefreshError("secret"), CalendarMetadataAuthenticationError),
        (GoogleAuthError("secret"), CalendarMetadataAuthenticationError),
        (TransportError("secret"), CalendarMetadataUnavailableError),
        (TimeoutError("secret"), CalendarMetadataUnavailableError),
        (OSError("secret"), CalendarMetadataUnavailableError),
        (HttpLib2Error("secret"), CalendarMetadataUnavailableError),
        (RequestException("secret"), CalendarMetadataUnavailableError),
    ],
)
def test_provider_failures_are_translated(
    service: MagicMock, error: Exception, expected: type[Exception]
) -> None:
    execute = service.calendars.return_value.get.return_value.execute
    execute.side_effect = error

    with pytest.raises(expected) as raised:
        GoogleCalendarReader().get_primary_calendar()

    assert raised.value.__cause__ is error
    if isinstance(raised.value, CalendarMetadataAuthenticationError):
        assert raised.value.provider is True
    execute.assert_called_once_with(num_retries=0)
    assert_client_closed(service)


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        "secret",
        {},
        {"summary": "Title"},
        {"summary": None, "timeZone": "UTC"},
        {"summary": 7, "timeZone": "UTC"},
        {"summary": "Title", "timeZone": 7},
    ],
)
def test_invalid_metadata(service: MagicMock, data: object) -> None:
    service.calendars.return_value.get.return_value.execute.return_value = data

    with pytest.raises(CalendarMetadataProviderError):
        GoogleCalendarReader().get_primary_calendar()

    assert_client_closed(service)


@pytest.mark.parametrize(
    "error", [FileNotFoundError("secret"), ValueError("secret"), RefreshError("secret")]
)
def test_local_auth_failure_skips_client(
    service: MagicMock, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    monkeypatch.setattr(
        "app.google_calendar.Credentials.from_authorized_user_file",
        MagicMock(side_effect=error),
    )
    with pytest.raises(CalendarMetadataAuthenticationError) as raised:
        GoogleCalendarReader().get_primary_calendar()

    assert raised.value.provider is False
    service.client_builder.assert_not_called()


def test_programming_error_is_not_relabelled(service: MagicMock) -> None:
    service.calendars.return_value.get.return_value.execute.side_effect = TypeError(
        "bug"
    )
    with pytest.raises(TypeError, match="bug"):
        GoogleCalendarReader().get_primary_calendar()
    assert_client_closed(service)
