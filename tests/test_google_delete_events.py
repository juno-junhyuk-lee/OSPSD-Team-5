from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import TransportError
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from httplib2 import HttpLib2Error, Response  # type: ignore[import-untyped]
from requests.exceptions import RequestException

from app import google_delete_events
from app.event_deletion_provider import (
    EventDeleter,
    EventDeletionNotFoundError,
    EventDeletionUnavailableError,
    EventDeletionUnconfirmedError,
)
from app.google_create_events import GoogleCalendarSetupError


@pytest.fixture
def deleter() -> EventDeleter:
    return google_delete_events.GoogleEventDeleter()


@pytest.fixture
def service() -> Iterator[MagicMock]:
    with (
        patch.object(google_delete_events, "load_credentials"),
        patch.object(google_delete_events, "build") as build,
    ):
        yield build.return_value.__enter__.return_value


def test_delete_event_calls_google_once(
    deleter: EventDeleter, service: MagicMock
) -> None:
    deleter.delete_event("google-event-1")

    delete = service.events.return_value.delete
    delete.assert_called_once_with(
        calendarId="primary", eventId="google-event-1", sendUpdates="none"
    )
    delete.return_value.execute.assert_called_once_with(num_retries=0)


@pytest.mark.parametrize("status", ["404", "410"])
def test_missing_or_deleted_event_is_not_found(
    deleter: EventDeleter, service: MagicMock, status: str
) -> None:
    error = HttpError(Response({"status": status}), b"")
    service.events.return_value.delete.return_value.execute.side_effect = error

    with pytest.raises(EventDeletionNotFoundError) as raised:
        deleter.delete_event("missing-event")

    assert raised.value.__cause__ is not None
    assert raised.value.__cause__.__cause__ is error


def test_unusable_authorization_is_unavailable(
    deleter: EventDeleter, service: MagicMock
) -> None:
    setup_error = GoogleCalendarSetupError("no token")
    with patch.object(
        google_delete_events, "load_credentials", side_effect=setup_error
    ):
        with pytest.raises(EventDeletionUnavailableError) as raised:
            deleter.delete_event("google-event-1")

    assert raised.value.__cause__ is setup_error
    service.events.return_value.delete.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        HttpError(Response({"status": "403"}), b'{"error": "denied"}'),
        HttpError(Response({"status": "500"}), b""),
        TimeoutError("Provider may have deleted the event."),
        TransportError("Private transport details"),
        HttpLib2Error("Private HTTP details"),
        RequestException("Private request details"),
        OSError("Private connection details"),
    ],
)
def test_provider_failure_is_unconfirmed_without_retry(
    deleter: EventDeleter, service: MagicMock, error: Exception
) -> None:
    execute = service.events.return_value.delete.return_value.execute
    execute.side_effect = error

    with pytest.raises(EventDeletionUnconfirmedError) as raised:
        deleter.delete_event("google-event-1")

    assert raised.value.__cause__ is error
    execute.assert_called_once_with(num_retries=0)
