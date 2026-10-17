import json
from typing import cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from google.auth.exceptions import TransportError
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from httplib2 import HttpLib2Error  # type: ignore[import-untyped]
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout as RequestsTimeout

from app.event_provider import (
    CalendarAuthenticationError,
    CalendarProviderError,
    EventAccessDeniedError,
    EventNotFoundError,
    EventReader,
    EventReadUnavailableError,
    UnsupportedEventError,
)
from app.google_events import GoogleEventReader


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> Mock:
    service = Mock()
    monkeypatch.setattr("app.google_events.calendar_client", lambda: service)
    return cast(Mock, service.events.return_value.get.return_value.execute)


def timed_event() -> dict[str, object]:
    return {
        "id": "google-event",
        "summary": "Provider meeting",
        "start": {"dateTime": "2026-10-05T10:00:00-04:00"},
        "end": {"dateTime": "2026-10-05T11:00:00-04:00"},
        "htmlLink": "https://example.com/private-provider-field",
    }


def test_google_fields_are_translated(client: TestClient, provider: Mock) -> None:
    provider.return_value = timed_event()

    response = client.get("/events/google-event")

    assert response.status_code == 200
    assert response.json() == {
        "id": "google-event",
        "title": "Provider meeting",
        "start_time": "2026-10-05T10:00:00-04:00",
        "end_time": "2026-10-05T11:00:00-04:00",
    }


def test_untitled_event_returns_empty_title(client: TestClient, provider: Mock) -> None:
    data = timed_event()
    del data["summary"]
    provider.return_value = data

    response = client.get("/events/google-event")

    assert response.status_code == 200
    assert response.json()["title"] == ""


def test_all_day_event_is_rejected(client: TestClient, provider: Mock) -> None:
    provider.return_value = {
        "id": "all-day",
        "summary": "All day",
        "start": {"date": "2026-10-05"},
        "end": {"date": "2026-10-06"},
    }

    response = client.get("/events/all-day")

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_input",
            "message": "Only timed events are supported.",
            "retryable": False,
        }
    }


@pytest.mark.parametrize(
    ("status", "expected_status", "code", "retryable"),
    [
        (403, 403, "access_denied", False),
        (429, 503, "provider_unavailable", True),
        (500, 503, "provider_unavailable", True),
        (503, 503, "provider_unavailable", True),
    ],
)
def test_provider_failure_is_not_not_found(
    client: TestClient,
    provider: Mock,
    status: int,
    expected_status: int,
    code: str,
    retryable: bool,
) -> None:
    provider.side_effect = HttpError(
        Mock(status=status, reason="Provider failure"),
        b'{"error": {"message": "Sensitive provider message"}}',
    )

    response = client.get("/events/google-event")

    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["retryable"] is retryable
    assert "Sensitive" not in response.text


def test_google_401_requires_authentication(
    client: TestClient, provider: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    provider.side_effect = HttpError(
        Mock(status=401, reason="Unauthorized"),
        b'{"error": {"message": "Sensitive provider message"}}',
    )

    response = client.get("/events/google-event")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "provider_unavailable",
            "message": "Calendar authentication required. Run scripts/google_calendar_auth.py.",
            "retryable": False,
        }
    }
    assert "Sensitive" not in response.text
    [record] = [
        record for record in caplog.records if record.name == "calendar_service"
    ]
    assert json.loads(record.getMessage()) == {
        "operation": "get_event",
        "error": "provider_unavailable",
        "provider": True,
        "status": 503,
    }
    assert "Sensitive" not in caplog.text


def test_network_failure_returns_service_unavailable(
    client: TestClient, provider: Mock
) -> None:
    provider.side_effect = TimeoutError("network timeout")

    response = client.get("/events/google-event")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "provider_unavailable",
            "message": "Calendar provider temporarily unavailable. Retry later.",
            "retryable": True,
        }
    }


@pytest.mark.parametrize(
    "data",
    [
        None,
        {"id": "broken"},
        {"id": "broken", "start": {}, "end": {}},
        {
            "id": "broken",
            "start": {"dateTime": "invalid"},
            "end": {"dateTime": "2026-10-05T11:00:00Z"},
        },
    ],
)
def test_malformed_provider_data_returns_bad_gateway(
    client: TestClient, provider: Mock, data: object
) -> None:
    provider.return_value = data

    response = client.get("/events/broken")

    assert response.status_code == 502
    assert response.json() == {
        "error": {
            "code": "provider_error",
            "message": "Calendar provider request failed.",
            "retryable": False,
        }
    }


def test_authentication_required_returns_service_unavailable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.google_events.calendar_client",
        Mock(side_effect=CalendarAuthenticationError),
    )

    response = client.get("/events/google-event")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "provider_unavailable",
            "message": "Calendar authentication required. Run scripts/google_calendar_auth.py.",
            "retryable": False,
        }
    }


@pytest.mark.parametrize(
    "outcome", ["success", "not-found", "http-error", "timeout", "malformed", "all-day"]
)
def test_google_client_is_closed_after_request(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    service = Mock()
    execute = service.events.return_value.get.return_value.execute
    execute.return_value = timed_event()
    expected_status = 200
    if outcome in {"not-found", "http-error"}:
        status = 404 if outcome == "not-found" else 500
        execute.side_effect = HttpError(
            Mock(status=status, reason="Failure"), b'{"error": {"message": "Failure"}}'
        )
        expected_status = 404 if status == 404 else 503
    elif outcome == "timeout":
        execute.side_effect = TimeoutError("timeout")
        expected_status = 503
    elif outcome == "malformed":
        execute.return_value = None
        expected_status = 502
    elif outcome == "all-day":
        execute.return_value = {
            "id": "all-day",
            "start": {"date": "2026-10-05"},
            "end": {"date": "2026-10-06"},
        }
        expected_status = 422
    monkeypatch.setattr("app.google_events.calendar_client", lambda: service)

    response = client.get("/events/google-event")

    assert response.status_code == expected_status
    service.close.assert_called_once_with()


def test_event_reader_translates_requested_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = Mock()
    service.events.return_value.get.return_value.execute.return_value = timed_event()
    monkeypatch.setattr("app.google_events.calendar_client", lambda: service)
    reader: EventReader = GoogleEventReader()

    event = reader.get_event("google-event")

    assert event.model_dump(mode="json") == {
        "id": "google-event",
        "title": "Provider meeting",
        "start_time": "2026-10-05T10:00:00-04:00",
        "end_time": "2026-10-05T11:00:00-04:00",
    }
    service.events.return_value.get.assert_called_once_with(
        calendarId="primary", eventId="google-event"
    )
    service.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("status", "reason", "expected"),
    [
        (401, "authError", CalendarAuthenticationError),
        (404, "notFound", EventNotFoundError),
        (403, "forbidden", EventAccessDeniedError),
        (403, "rateLimitExceeded", EventReadUnavailableError),
        (403, "userRateLimitExceeded", EventReadUnavailableError),
        (403, "quotaExceeded", EventReadUnavailableError),
        (408, "timeout", EventReadUnavailableError),
        (429, "rateLimitExceeded", EventReadUnavailableError),
        (500, "backendError", EventReadUnavailableError),
        (502, "badGateway", EventReadUnavailableError),
        (503, "unavailable", EventReadUnavailableError),
        (504, "timeout", EventReadUnavailableError),
        (400, "badRequest", CalendarProviderError),
        (409, "conflict", CalendarProviderError),
    ],
)
def test_reader_translates_http_failures(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    reason: str,
    expected: type[Exception],
) -> None:
    service = Mock()
    failure = HttpError(
        Mock(status=status, reason="Sensitive provider reason"),
        json.dumps(
            {"error": {"message": "Sensitive message", "errors": [{"reason": reason}]}}
        ).encode(),
    )
    execute = service.events.return_value.get.return_value.execute
    execute.side_effect = failure
    monkeypatch.setattr("app.google_events.calendar_client", lambda: service)

    with pytest.raises(expected) as raised:
        GoogleEventReader().get_event("google-event")

    assert type(raised.value) is expected
    assert raised.value.__cause__ is failure
    assert str(raised.value) == ""
    if isinstance(raised.value, CalendarAuthenticationError):
        assert raised.value.provider is True
    execute.assert_called_once_with()
    service.close.assert_called_once_with()


@pytest.mark.parametrize(
    "failure",
    [
        TimeoutError("Sensitive timeout"),
        ConnectionError("Sensitive connection"),
        TransportError("Sensitive transport"),
        HttpLib2Error("Sensitive HTTP transport"),
        RequestsTimeout("Sensitive requests timeout"),
        RequestsConnectionError("Sensitive requests connection"),
    ],
)
def test_reader_translates_transport_failure(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    service = Mock()
    execute = service.events.return_value.get.return_value.execute
    execute.side_effect = failure
    monkeypatch.setattr("app.google_events.calendar_client", lambda: service)

    with pytest.raises(EventReadUnavailableError) as raised:
        GoogleEventReader().get_event("google-event")

    assert raised.value.__cause__ is failure
    assert str(raised.value) == ""
    execute.assert_called_once_with()
    service.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (None, CalendarProviderError),
        ({"id": "broken"}, CalendarProviderError),
        ({"id": "broken", "start": {}, "end": {}}, CalendarProviderError),
        (
            {
                "id": "broken",
                "start": {"dateTime": "invalid"},
                "end": {"dateTime": "2026-10-05T11:00:00Z"},
            },
            CalendarProviderError,
        ),
        (
            {
                "id": "all-day",
                "start": {"date": "2026-10-05"},
                "end": {"date": "2026-10-06"},
            },
            UnsupportedEventError,
        ),
    ],
)
def test_reader_distinguishes_invalid_and_unsupported_data(
    monkeypatch: pytest.MonkeyPatch, data: object, expected: type[Exception]
) -> None:
    service = Mock()
    service.events.return_value.get.return_value.execute.return_value = data
    monkeypatch.setattr("app.google_events.calendar_client", lambda: service)

    with pytest.raises(expected) as raised:
        GoogleEventReader().get_event("google-event")

    assert type(raised.value) is expected
    service.close.assert_called_once_with()


def test_reader_preserves_authorization_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = CalendarAuthenticationError()
    monkeypatch.setattr("app.google_events.calendar_client", Mock(side_effect=failure))

    with pytest.raises(CalendarAuthenticationError) as raised:
        GoogleEventReader().get_event("google-event")

    assert raised.value is failure


def test_reader_does_not_hide_programming_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = Mock()
    failure = TypeError("Unexpected programming error")
    service.events.return_value.get.return_value.execute.side_effect = failure
    monkeypatch.setattr("app.google_events.calendar_client", lambda: service)

    with pytest.raises(TypeError) as raised:
        GoogleEventReader().get_event("google-event")

    assert raised.value is failure
    service.close.assert_called_once_with()
