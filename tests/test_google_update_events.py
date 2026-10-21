from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import TransportError
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from httplib2 import HttpLib2Error, Response  # type: ignore[import-untyped]
from pydantic import ValidationError
from requests.exceptions import RequestException

from app import google_create_events, google_update_events
from app.event_update_provider import (
    EventUpdateDeniedError,
    EventUpdateNotFoundError,
    EventUpdater,
    EventUpdateUnavailableError,
    EventUpdateUnconfirmedError,
)
from app.models import UpdateEventRequest


@pytest.fixture
def updater() -> EventUpdater:
    return google_update_events.GoogleEventUpdater()


@pytest.fixture
def update_request() -> UpdateEventRequest:
    return UpdateEventRequest.model_validate(
        {
            "title": "  Updated Meeting  ",
            "start_time": "2026-10-06T11:00:00-04:00",
            "end_time": "2026-10-06T12:00:00-04:00",
        }
    )


@pytest.fixture
def provider_response() -> dict[str, object]:
    return {
        "id": "test-event",
        "summary": "Updated Meeting",
        "start": {"dateTime": "2026-10-06T15:00:00Z"},
        "end": {"dateTime": "2026-10-06T16:00:00Z"},
        "htmlLink": "https://calendar.google.com/example",
    }


@pytest.fixture
def service(provider_response: dict[str, object]) -> Iterator[MagicMock]:
    with (
        patch.object(google_update_events, "load_credentials"),
        patch.object(google_update_events, "build") as build,
    ):
        sdk = build.return_value.__enter__.return_value
        sdk.events.return_value.get.return_value.execute.return_value = {
            "id": "test-event",
            "status": "confirmed",
            "summary": "Original",
            "start": {"dateTime": "2026-10-06T14:00:00Z"},
            "end": {"dateTime": "2026-10-06T15:00:00Z"},
        }
        sdk.events.return_value.patch.return_value.execute.return_value = (
            provider_response
        )
        yield sdk


def test_update_translates_google_fields(
    updater: EventUpdater, update_request: UpdateEventRequest, service: MagicMock
) -> None:
    event = updater.update_event("test-event", update_request)

    service.events.return_value.get.assert_called_once_with(
        calendarId="primary", eventId="test-event"
    )
    service.events.return_value.patch.assert_called_once_with(
        calendarId="primary",
        eventId="test-event",
        body={
            "summary": "Updated Meeting",
            "start": {"dateTime": "2026-10-06T11:00:00-04:00"},
            "end": {"dateTime": "2026-10-06T12:00:00-04:00"},
        },
    )
    assert event.model_dump(mode="json") == {
        "id": "test-event",
        "title": "Updated Meeting",
        "start_time": "2026-10-06T15:00:00Z",
        "end_time": "2026-10-06T16:00:00Z",
    }


def test_cancelled_existing_event_raises_not_found(
    updater: EventUpdater, update_request: UpdateEventRequest, service: MagicMock
) -> None:
    service.events.return_value.get.return_value.execute.return_value = {
        "id": "test-event",
        "status": "cancelled",
        "summary": "Gone",
        "start": {"dateTime": "2026-10-06T14:00:00Z"},
        "end": {"dateTime": "2026-10-06T15:00:00Z"},
    }

    with pytest.raises(EventUpdateNotFoundError):
        updater.update_event("test-event", update_request)

    service.events.return_value.patch.assert_not_called()


def test_missing_authorization_raises_unavailable(
    updater: EventUpdater, update_request: UpdateEventRequest
) -> None:
    with patch.object(
        google_update_events,
        "load_credentials",
        side_effect=google_create_events.GoogleCalendarSetupError("no token"),
    ):
        with pytest.raises(EventUpdateUnavailableError) as raised:
            updater.update_event("test-event", update_request)

    assert raised.value.provider is False


def test_remote_authorization_refusal_raises_unavailable(
    updater: EventUpdater, update_request: UpdateEventRequest, service: MagicMock
) -> None:
    error = HttpError(Response({"status": "401"}), b"")
    service.events.return_value.patch.return_value.execute.side_effect = error

    with pytest.raises(EventUpdateUnavailableError) as raised:
        updater.update_event("test-event", update_request)

    assert raised.value.provider is True
    assert raised.value.__cause__ is error


def test_permission_refusal_is_denied(
    updater: EventUpdater, update_request: UpdateEventRequest, service: MagicMock
) -> None:
    error = HttpError(Response({"status": "403"}), b'{"error": "denied"}')
    service.events.return_value.patch.return_value.execute.side_effect = error

    with pytest.raises(EventUpdateDeniedError) as raised:
        updater.update_event("test-event", update_request)

    assert raised.value.__cause__ is error


@pytest.mark.parametrize(
    "failure",
    [
        HttpError(
            Response({"status": "403"}),
            b'{"error": {"message": "Rate Limit Exceeded", "errors": [{"reason": "rateLimitExceeded"}]}}',
        ),
        HttpError(Response({"status": "500"}), b""),
        TransportError("transport"),
        HttpLib2Error("httplib2"),
        RequestException("requests"),
        OSError("os"),
        ValidationError.from_exception_data("Event", []),
    ],
)
def test_provider_failure_raises_unconfirmed(
    updater: EventUpdater,
    update_request: UpdateEventRequest,
    service: MagicMock,
    failure: Exception,
) -> None:
    service.events.return_value.patch.return_value.execute.side_effect = failure

    with pytest.raises(EventUpdateUnconfirmedError) as raised:
        updater.update_event("test-event", update_request)

    assert raised.value.__cause__ is failure
