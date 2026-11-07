from typing import cast
from unittest.mock import Mock

import pytest
from calendar_contract import (
    CalendarError,
    CalendarService,
    CreateEvent,
    ErrorCode,
    Event,
    ReplaceEvent,
)

from app.calendar_service import GoogleCalendarService
from app.event_creation_provider import (
    EventCreationDeniedError,
    EventCreationProviderUnavailableError,
    EventCreationUnavailableError,
    EventCreationUnconfirmedError,
    EventCreator,
)
from app.event_deletion_provider import (
    EventDeleter,
    EventDeletionDeniedError,
    EventDeletionNotFoundError,
    EventDeletionProviderUnavailableError,
    EventDeletionUnavailableError,
    EventDeletionUnconfirmedError,
)
from app.event_provider import (
    CalendarAuthenticationError,
    CalendarProviderError,
    EventAccessDeniedError,
    EventNotFoundError,
    EventReader,
    EventReadUnavailableError,
    UnsupportedEventError,
)
from app.event_update_provider import (
    EventUpdateDeniedError,
    EventUpdateNotFoundError,
    EventUpdateProviderError,
    EventUpdateProviderUnavailableError,
    EventUpdater,
    EventUpdateUnavailableError,
    EventUpdateUnconfirmedError,
)

FIELDS = {
    "title": "Service check",
    "start": "2030-01-07T15:00:00Z",
    "end": "2030-01-07T15:30:00Z",
}
METHODS = {
    "create": "create_event",
    "get": "get_event",
    "replace": "update_event",
    "delete": "delete_event",
}


@pytest.fixture
def providers() -> dict[str, Mock]:
    return {
        "create": Mock(spec=EventCreator),
        "get": Mock(spec=EventReader),
        "replace": Mock(spec=EventUpdater),
        "delete": Mock(spec=EventDeleter),
    }


@pytest.fixture
def service(providers: dict[str, Mock]) -> CalendarService:
    return GoogleCalendarService(
        creator=cast(EventCreator, providers["create"]),
        reader=cast(EventReader, providers["get"]),
        updater=cast(EventUpdater, providers["replace"]),
        deleter=cast(EventDeleter, providers["delete"]),
    )


def call_operation(service: CalendarService, operation: str) -> Event | None:
    if operation == "create":
        return service.create(CreateEvent(**FIELDS))
    if operation == "get":
        return service.get("test-event")
    if operation == "replace":
        return service.replace("test-event", ReplaceEvent(**FIELDS))
    service.delete("test-event")
    return None


@pytest.mark.parametrize("operation", METHODS)
def test_shared_service_delegates_once(
    service: CalendarService, providers: dict[str, Mock], operation: str
) -> None:
    event = Event(id="test-event", **FIELDS)
    method = getattr(providers[operation], METHODS[operation])
    method.return_value = None if operation == "delete" else event

    result = call_operation(service, operation)

    assert result is (None if operation == "delete" else event)
    if operation == "create":
        method.assert_called_once_with(CreateEvent(**FIELDS))
    elif operation == "replace":
        method.assert_called_once_with("test-event", ReplaceEvent(**FIELDS))
    else:
        method.assert_called_once_with("test-event")
    for other in METHODS:
        if other != operation:
            assert providers[other].mock_calls == []


@pytest.mark.parametrize(
    ("operation", "failure", "code", "retryable", "provider"),
    [
        (
            "create",
            EventCreationDeniedError("private"),
            ErrorCode.ACCESS_DENIED,
            False,
            True,
        ),
        (
            "get",
            EventAccessDeniedError("private"),
            ErrorCode.ACCESS_DENIED,
            False,
            True,
        ),
        (
            "replace",
            EventUpdateDeniedError("private"),
            ErrorCode.ACCESS_DENIED,
            False,
            True,
        ),
        (
            "delete",
            EventDeletionDeniedError("private"),
            ErrorCode.ACCESS_DENIED,
            False,
            True,
        ),
        (
            "create",
            EventCreationUnavailableError("private"),
            ErrorCode.PROVIDER_UNAVAILABLE,
            False,
            False,
        ),
        (
            "get",
            CalendarAuthenticationError("private"),
            ErrorCode.PROVIDER_UNAVAILABLE,
            False,
            False,
        ),
        (
            "replace",
            EventUpdateUnavailableError("private"),
            ErrorCode.PROVIDER_UNAVAILABLE,
            False,
            False,
        ),
        (
            "delete",
            EventDeletionUnavailableError("private"),
            ErrorCode.PROVIDER_UNAVAILABLE,
            False,
            False,
        ),
        (
            "create",
            EventCreationProviderUnavailableError("private"),
            ErrorCode.PROVIDER_UNAVAILABLE,
            True,
            True,
        ),
        (
            "get",
            EventReadUnavailableError("private"),
            ErrorCode.PROVIDER_UNAVAILABLE,
            True,
            True,
        ),
        (
            "replace",
            EventUpdateProviderUnavailableError("private"),
            ErrorCode.PROVIDER_UNAVAILABLE,
            True,
            True,
        ),
        (
            "delete",
            EventDeletionProviderUnavailableError("private"),
            ErrorCode.PROVIDER_UNAVAILABLE,
            True,
            True,
        ),
        ("get", EventNotFoundError("private"), ErrorCode.NOT_FOUND, False, True),
        (
            "replace",
            EventUpdateNotFoundError("private"),
            ErrorCode.NOT_FOUND,
            False,
            True,
        ),
        (
            "delete",
            EventDeletionNotFoundError("private"),
            ErrorCode.NOT_FOUND,
            False,
            True,
        ),
        (
            "create",
            EventCreationUnconfirmedError("private"),
            ErrorCode.PROVIDER_ERROR,
            False,
            True,
        ),
        (
            "replace",
            EventUpdateUnconfirmedError("private"),
            ErrorCode.PROVIDER_ERROR,
            False,
            True,
        ),
        (
            "delete",
            EventDeletionUnconfirmedError("private"),
            ErrorCode.PROVIDER_ERROR,
            True,
            True,
        ),
        (
            "get",
            CalendarProviderError("private"),
            ErrorCode.PROVIDER_ERROR,
            False,
            True,
        ),
        (
            "replace",
            EventUpdateProviderError("private"),
            ErrorCode.PROVIDER_ERROR,
            False,
            True,
        ),
        ("get", UnsupportedEventError("private"), ErrorCode.INVALID_INPUT, False, True),
    ],
)
def test_operation_failure_crosses_python_boundary_as_calendar_error(
    service: CalendarService,
    providers: dict[str, Mock],
    operation: str,
    failure: Exception,
    code: ErrorCode,
    retryable: bool,
    provider: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    method = getattr(providers[operation], METHODS[operation])
    method.side_effect = failure

    with pytest.raises(CalendarError) as raised:
        call_operation(service, operation)

    assert raised.value.code == code
    assert raised.value.retryable is retryable
    assert raised.value.details == {"provider": provider}
    assert "private" not in str(raised.value)
    assert method.call_count == 1
    assert not [r for r in caplog.records if r.name == "calendar_service"]


@pytest.mark.parametrize("operation", METHODS)
def test_service_does_not_hide_programming_errors(
    service: CalendarService, providers: dict[str, Mock], operation: str
) -> None:
    failure = TypeError("Programming error")
    getattr(providers[operation], METHODS[operation]).side_effect = failure

    with pytest.raises(TypeError) as raised:
        call_operation(service, operation)

    assert raised.value is failure
