import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import RefreshError, TransportError
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from httplib2 import HttpLib2Error, Response  # type: ignore[import-untyped]
from pydantic import ValidationError
from requests.exceptions import RequestException

from app import google_create_events
from app.event_creation_provider import (
    EventCreationDeniedError,
    EventCreationUnavailableError,
    EventCreationUnconfirmedError,
    EventCreator,
)
from app.models import CreateEventRequest


@pytest.fixture
def creator() -> EventCreator:
    return google_create_events.GoogleEventCreator()


@pytest.fixture
def creation_request() -> CreateEventRequest:
    return CreateEventRequest.model_validate(
        {
            "title": "  Team Meeting  ",
            "start_time": "2026-10-05T10:00:00-04:00",
            "end_time": "2026-10-05T09:00:00-06:00",
        }
    )


@pytest.fixture
def provider_response() -> dict[str, object]:
    return {
        "id": "google-event-123",
        "summary": "Team Meeting",
        "start": {"dateTime": "2026-10-05T14:00:00Z"},
        "end": {"dateTime": "2026-10-05T15:00:00Z"},
        "htmlLink": "https://calendar.google.com/example",
        "organizer": {"email": "example@example.com"},
    }


@pytest.fixture
def service(provider_response: dict[str, object]) -> Iterator[MagicMock]:
    with (
        patch.object(google_create_events, "load_credentials"),
        patch.object(google_create_events, "build") as build,
    ):
        sdk = build.return_value.__enter__.return_value
        sdk.events.return_value.insert.return_value.execute.return_value = (
            provider_response
        )
        yield sdk


def test_create_translates_google_fields(
    creator: EventCreator, creation_request: CreateEventRequest, service: MagicMock
) -> None:
    event = creator.create_event(creation_request)

    service.events.return_value.insert.assert_called_once_with(
        calendarId="primary",
        body={
            "summary": "Team Meeting",
            "start": {"dateTime": "2026-10-05T10:00:00-04:00"},
            "end": {"dateTime": "2026-10-05T09:00:00-06:00"},
        },
    )
    assert event.model_dump(mode="json") == {
        "id": "google-event-123",
        "title": "Team Meeting",
        "start_time": "2026-10-05T14:00:00Z",
        "end_time": "2026-10-05T15:00:00Z",
    }
    assert event.start_time == creation_request.start_time
    assert event.end_time == creation_request.end_time


def test_repeated_creation_returns_provider_ids(
    creator: EventCreator,
    creation_request: CreateEventRequest,
    service: MagicMock,
    provider_response: dict[str, object],
) -> None:
    execute = service.events.return_value.insert.return_value.execute
    execute.side_effect = [
        {**provider_response, "id": "google-first-event"},
        {**provider_response, "id": "google-second-event"},
    ]

    first = creator.create_event(creation_request)
    second = creator.create_event(creation_request)

    assert first.id == "google-first-event"
    assert second.id == "google-second-event"
    assert execute.call_count == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", ""),
        ("summary", ""),
        ("start", {"date": "2026-10-05"}),
        ("start", {"dateTime": "2026-10-05T14:00:00"}),
        ("end", {"dateTime": "2026-10-05T14:00:00Z"}),
    ],
)
def test_unusable_provider_response_is_not_a_success(
    creator: EventCreator,
    creation_request: CreateEventRequest,
    service: MagicMock,
    provider_response: dict[str, object],
    field: str,
    value: object,
) -> None:
    provider_response[field] = value

    with pytest.raises(EventCreationUnconfirmedError) as raised:
        creator.create_event(creation_request)

    assert isinstance(raised.value.__cause__, ValidationError)


@pytest.mark.parametrize(
    "error",
    [
        HttpError(Response({"status": "429"}), b'{"error": "rate limited"}'),
        HttpError(Response({"status": "500"}), b'{"error": "provider failure"}'),
        TimeoutError("Provider may have accepted the write."),
        TransportError("Private transport details"),
        HttpLib2Error("Private HTTP details"),
        RequestException("Private request details"),
        OSError("Private connection details"),
    ],
)
def test_provider_failure_does_not_retry(
    creator: EventCreator,
    creation_request: CreateEventRequest,
    service: MagicMock,
    error: Exception,
) -> None:
    execute = service.events.return_value.insert.return_value.execute
    execute.side_effect = error

    with pytest.raises(EventCreationUnconfirmedError) as raised:
        creator.create_event(creation_request)

    assert raised.value.__cause__ is error
    execute.assert_called_once_with(num_retries=0)
    google_create_events.build.return_value.__exit__.assert_called_once()  # type: ignore[attr-defined]


def test_permission_denial_is_distinct_from_uncertain_creation(
    creator: EventCreator,
    creation_request: CreateEventRequest,
    service: MagicMock,
) -> None:
    error = HttpError(
        Response({"status": "403"}),
        b'{"error": {"errors": [{"reason": "forbidden"}], "message": "private"}}',
    )
    execute = service.events.return_value.insert.return_value.execute
    execute.side_effect = error

    with pytest.raises(EventCreationDeniedError) as raised:
        creator.create_event(creation_request)

    assert raised.value.__cause__ is error
    assert "private" not in str(raised.value)
    execute.assert_called_once_with(num_retries=0)


@pytest.mark.parametrize(
    "reason", ["rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded"]
)
def test_rate_limit_403_is_not_permission_denial(
    creator: EventCreator,
    creation_request: CreateEventRequest,
    service: MagicMock,
    reason: str,
) -> None:
    error = HttpError(
        Response({"status": "403"}),
        json.dumps(
            {"error": {"message": "Quota limit", "errors": [{"reason": reason}]}}
        ).encode(),
    )
    execute = service.events.return_value.insert.return_value.execute
    execute.side_effect = error

    with pytest.raises(EventCreationUnconfirmedError) as raised:
        creator.create_event(creation_request)

    assert raised.value.__cause__ is error
    execute.assert_called_once_with(num_retries=0)


@pytest.mark.parametrize(
    "error",
    [
        HttpError(Response({"status": "401"}), b'{"error": "private token"}'),
        RefreshError("Private refresh failure during insertion"),
    ],
)
def test_remote_authorization_failure_is_unavailable(
    creator: EventCreator,
    creation_request: CreateEventRequest,
    service: MagicMock,
    error: Exception,
) -> None:
    execute = service.events.return_value.insert.return_value.execute
    execute.side_effect = error

    with pytest.raises(EventCreationUnavailableError) as raised:
        creator.create_event(creation_request)

    assert raised.value.provider is True
    assert raised.value.__cause__ is error
    assert "Private" not in str(raised.value)
    execute.assert_called_once_with(num_retries=0)


def test_unexpected_programming_error_is_not_hidden(
    creator: EventCreator,
    creation_request: CreateEventRequest,
    service: MagicMock,
) -> None:
    service.events.return_value.insert.return_value.execute.side_effect = TypeError(
        "Programming defect"
    )

    with pytest.raises(TypeError, match="Programming defect"):
        creator.create_event(creation_request)


@pytest.fixture
def local_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    token_path = tmp_path / "token.json"
    monkeypatch.setattr(google_create_events, "TOKEN_PATH", token_path)
    return token_path


def test_missing_token_prevents_provider_creation(
    creator: EventCreator, creation_request: CreateEventRequest, local_token: Path
) -> None:
    with patch.object(google_create_events, "build") as build:
        with pytest.raises(EventCreationUnavailableError) as raised:
            creator.create_event(creation_request)

    assert isinstance(
        raised.value.__cause__, google_create_events.GoogleCalendarSetupError
    )
    assert raised.value.provider is False
    build.assert_not_called()
    assert not local_token.exists()


def test_malformed_token_reports_setup_problem(local_token: Path) -> None:
    local_token.write_text("not JSON", encoding="utf-8")

    with pytest.raises(google_create_events.GoogleCalendarSetupError):
        google_create_events.load_credentials()

    assert local_token.read_text(encoding="utf-8") == "not JSON"


@pytest.fixture
def credentials() -> Iterator[MagicMock]:
    with patch.object(Credentials, "from_authorized_user_file") as load:
        credentials = load.return_value
        credentials.valid = True
        credentials.has_scopes.return_value = True
        yield credentials


def test_valid_token_is_reused(local_token: Path, credentials: MagicMock) -> None:
    assert google_create_events.load_credentials() is credentials
    credentials.refresh.assert_not_called()
    assert not local_token.exists()


def test_refresh_saves_usable_token(local_token: Path, credentials: MagicMock) -> None:
    credentials.valid = False
    credentials.expired = True
    credentials.refresh_token = "test-refresh-token"
    credentials.to_json.return_value = '{"token": "test-refreshed-token"}'

    def refresh(_: object) -> None:
        credentials.valid = True

    credentials.refresh.side_effect = refresh

    with patch.object(google_create_events, "Request"):
        assert google_create_events.load_credentials() is credentials

    credentials.refresh.assert_called_once()
    assert local_token.read_text(encoding="utf-8") == (
        '{"token": "test-refreshed-token"}'
    )


@pytest.mark.parametrize("problem", ["scope", "unrefreshable", "revoked", "invalid"])
def test_unusable_authorization_does_not_save_token(
    local_token: Path, credentials: MagicMock, problem: str
) -> None:
    credentials.valid = False
    credentials.expired = True
    credentials.refresh_token = "test-refresh-token"
    if problem == "scope":
        credentials.has_scopes.return_value = False
    elif problem == "unrefreshable":
        credentials.refresh_token = None
    elif problem == "revoked":
        credentials.refresh.side_effect = RefreshError("Test token revoked")

    with patch.object(google_create_events, "Request"):
        with pytest.raises(google_create_events.GoogleCalendarSetupError):
            google_create_events.load_credentials()

    assert not local_token.exists()
    if problem in ("scope", "unrefreshable"):
        credentials.refresh.assert_not_called()


@pytest.mark.parametrize("problem", ["revoked", "invalid"])
def test_refresh_failure_records_remote_involvement_without_insert(
    creator: EventCreator,
    creation_request: CreateEventRequest,
    local_token: Path,
    credentials: MagicMock,
    problem: str,
) -> None:
    credentials.valid = False
    credentials.expired = True
    credentials.refresh_token = "test-refresh-token"
    if problem == "revoked":
        credentials.refresh.side_effect = RefreshError("Private revoked token")

    with (
        patch.object(google_create_events, "Request"),
        patch.object(google_create_events, "build") as build,
    ):
        with pytest.raises(EventCreationUnavailableError) as raised:
            creator.create_event(creation_request)

    assert raised.value.provider is True
    credentials.refresh.assert_called_once()
    build.assert_not_called()
    assert not local_token.exists()
