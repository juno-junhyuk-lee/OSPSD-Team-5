from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from httplib2 import Response  # type: ignore[import-untyped]
from pydantic import ValidationError

from app import google_create_events
from app.models import CreateEventRequest


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
    creation_request: CreateEventRequest, service: MagicMock
) -> None:
    event = google_create_events.create_google_event(creation_request)

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
    creation_request: CreateEventRequest,
    service: MagicMock,
    provider_response: dict[str, object],
) -> None:
    execute = service.events.return_value.insert.return_value.execute
    execute.side_effect = [
        {**provider_response, "id": "google-first-event"},
        {**provider_response, "id": "google-second-event"},
    ]

    first = google_create_events.create_google_event(creation_request)
    second = google_create_events.create_google_event(creation_request)

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
    creation_request: CreateEventRequest,
    service: MagicMock,
    provider_response: dict[str, object],
    field: str,
    value: object,
) -> None:
    provider_response[field] = value

    with pytest.raises(ValidationError):
        google_create_events.create_google_event(creation_request)


@pytest.mark.parametrize(
    "error",
    [
        HttpError(Response({"status": "403"}), b'{"error": "denied"}'),
        TimeoutError("Provider may have accepted the write."),
    ],
)
def test_provider_failure_does_not_retry(
    creation_request: CreateEventRequest, service: MagicMock, error: Exception
) -> None:
    execute = service.events.return_value.insert.return_value.execute
    execute.side_effect = error

    with pytest.raises(type(error)):
        google_create_events.create_google_event(creation_request)

    execute.assert_called_once_with(num_retries=0)


@pytest.fixture
def local_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    token_path = tmp_path / "token.json"
    monkeypatch.setattr(google_create_events, "TOKEN_PATH", token_path)
    return token_path


def test_missing_token_prevents_provider_creation(
    creation_request: CreateEventRequest, local_token: Path
) -> None:
    with patch.object(google_create_events, "build") as build:
        with pytest.raises(google_create_events.GoogleCalendarSetupError):
            google_create_events.create_google_event(creation_request)

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
