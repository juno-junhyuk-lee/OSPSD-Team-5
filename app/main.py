import re
from typing import Annotated

from fastapi import Depends, FastAPI, Response
from fastapi.exceptions import RequestValidationError

from app.calendar_dependencies import get_calendar_reader
from app.calendar_provider import (
    CalendarMetadataAccessDeniedError,
    CalendarMetadataAuthenticationError,
    CalendarMetadataNotFoundError,
    CalendarMetadataProviderError,
    CalendarMetadataUnavailableError,
    CalendarReader,
)
from app.errors import (
    ErrorCode,
    ErrorResponse,
    ServiceError,
    request_validation_handler,
    service_error_handler,
)
from app.event_creation_dependencies import get_event_creator
from app.event_creation_provider import (
    EventCreationDeniedError,
    EventCreationUnavailableError,
    EventCreationUnconfirmedError,
    EventCreator,
)
from app.event_deletion_dependencies import get_event_deleter
from app.event_deletion_provider import (
    EventDeleter,
    EventDeletionDeniedError,
    EventDeletionNotFoundError,
    EventDeletionUnavailableError,
    EventDeletionUnconfirmedError,
)
from app.event_dependencies import get_event_reader
from app.event_provider import (
    CalendarAuthenticationError,
    CalendarProviderError,
    EventAccessDeniedError,
    EventNotFoundError,
    EventReader,
    EventReadUnavailableError,
    UnsupportedEventError,
)
from app.event_update_dependencies import get_event_updater
from app.event_update_provider import (
    EventUpdateDeniedError,
    EventUpdateNotFoundError,
    EventUpdater,
    EventUpdateUnavailableError,
    EventUpdateUnconfirmedError,
)
from app.models import Calendar, CreateEventRequest, Event, UpdateEventRequest

app = FastAPI(
    title="Calendar Service",
    responses={422: {"model": ErrorResponse, "description": "Invalid request"}},
)
app.add_exception_handler(ServiceError, service_error_handler)
app.add_exception_handler(RequestValidationError, request_validation_handler)

# Google event IDs, including recurring instances, use only these characters.
EVENT_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,1024}")


@app.get("/calendars/{calendar_id}", response_model=Calendar)
def get_calendar(
    calendar_id: str,
    reader: Annotated[CalendarReader, Depends(get_calendar_reader)],
) -> Calendar:
    """Retrieve the authenticated user's primary calendar metadata."""
    if calendar_id != "primary":
        raise ServiceError(
            ErrorCode.NOT_FOUND,
            "Calendar not found.",
            operation="get_calendar",
            retryable=False,
            provider=False,
        )
    try:
        return reader.get_primary_calendar()
    except CalendarMetadataNotFoundError:
        raise ServiceError(
            ErrorCode.NOT_FOUND,
            "Calendar not found.",
            operation="get_calendar",
            retryable=False,
            provider=True,
        ) from None
    except CalendarMetadataAuthenticationError as error:
        raise ServiceError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "Calendar authentication required. Run scripts/google_calendar_auth.py.",
            operation="get_calendar",
            retryable=False,
            provider=error.provider,
        ) from None
    except CalendarMetadataAccessDeniedError:
        raise ServiceError(
            ErrorCode.ACCESS_DENIED,
            "Calendar access denied.",
            operation="get_calendar",
            retryable=False,
            provider=True,
        ) from None
    except CalendarMetadataUnavailableError:
        raise ServiceError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "Calendar provider temporarily unavailable.",
            operation="get_calendar",
            retryable=True,
            provider=True,
        ) from None
    except CalendarMetadataProviderError:
        raise ServiceError(
            ErrorCode.PROVIDER_ERROR,
            "Calendar provider request failed.",
            operation="get_calendar",
            retryable=False,
            provider=True,
        ) from None


@app.get("/events/{event_id}", response_model=Event)
def get_event(
    event_id: str,
    reader: Annotated[EventReader, Depends(get_event_reader)],
) -> Event:
    """Retrieve one timed event from the authenticated primary Google Calendar."""
    if not EVENT_ID_PATTERN.fullmatch(event_id):
        raise ServiceError(
            ErrorCode.INVALID_INPUT,
            "Event ID must be 1-1024 letters, digits, '_' or '-'.",
            operation="get_event",
            retryable=False,
            provider=False,
        )
    try:
        return reader.get_event(event_id)
    except EventNotFoundError:
        raise ServiceError(
            ErrorCode.NOT_FOUND,
            "Event not found.",
            operation="get_event",
            retryable=False,
            provider=True,
        ) from None
    except CalendarAuthenticationError as error:
        raise ServiceError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "Calendar authentication required. Run scripts/google_calendar_auth.py.",
            operation="get_event",
            retryable=False,
            provider=error.provider,
        ) from None
    except UnsupportedEventError:
        raise ServiceError(
            ErrorCode.INVALID_INPUT,
            "Only timed events are supported.",
            operation="get_event",
            retryable=False,
            provider=True,
        ) from None
    except EventAccessDeniedError:
        raise ServiceError(
            ErrorCode.ACCESS_DENIED,
            "Calendar denied access to this event.",
            operation="get_event",
            retryable=False,
            provider=True,
        ) from None
    except EventReadUnavailableError:
        raise ServiceError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "Calendar provider temporarily unavailable. Retry later.",
            operation="get_event",
            retryable=True,
            provider=True,
        ) from None
    except CalendarProviderError:
        raise ServiceError(
            ErrorCode.PROVIDER_ERROR,
            "Calendar provider request failed.",
            operation="get_event",
            retryable=False,
            provider=True,
        ) from None


@app.post(
    "/events",
    response_model=Event,
    status_code=201,
    responses={
        403: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def create_event(
    request: CreateEventRequest,
    creator: Annotated[EventCreator, Depends(get_event_creator)],
) -> Event:
    """Create a timed Google event and return its provider-assigned ID."""
    try:
        event = creator.create_event(request)
    except EventCreationUnavailableError as error:
        raise ServiceError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "Google Calendar authorization is unavailable. "
            "Run scripts/google_calendar_auth.py.",
            operation="create_event",
            retryable=False,
            provider=error.provider,
        ) from None
    except EventCreationDeniedError:
        raise ServiceError(
            ErrorCode.ACCESS_DENIED,
            "Google Calendar denied permission to create this event.",
            operation="create_event",
            retryable=False,
            provider=True,
        ) from None
    except EventCreationUnconfirmedError:
        raise ServiceError(
            ErrorCode.PROVIDER_ERROR,
            "Google Calendar creation could not be confirmed. "
            "Check the calendar before retrying.",
            operation="create_event",
            retryable=False,
            provider=True,
        ) from None
    return event


@app.patch(
    "/events/{event_id}",
    response_model=Event,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def update_event(
    event_id: str,
    request: UpdateEventRequest,
    updater: Annotated[EventUpdater, Depends(get_event_updater)],
) -> Event:
    """Update a timed Google event and return the refreshed Event fields."""
    if not EVENT_ID_PATTERN.fullmatch(event_id):
        raise ServiceError(
            ErrorCode.INVALID_INPUT,
            "Event ID must be 1-1024 letters, digits, '_' or '-'.",
            operation="update_event",
            retryable=False,
            provider=False,
        )
    try:
        return updater.update_event(event_id, request)
    except EventUpdateNotFoundError:
        raise ServiceError(
            ErrorCode.NOT_FOUND,
            "Event not found.",
            operation="update_event",
            retryable=False,
            provider=True,
        ) from None
    except EventUpdateDeniedError:
        raise ServiceError(
            ErrorCode.ACCESS_DENIED,
            "Google Calendar denied permission to update this event.",
            operation="update_event",
            retryable=False,
            provider=True,
        ) from None
    except EventUpdateUnavailableError as error:
        raise ServiceError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "Google Calendar authorization is unavailable. "
            "Run scripts/google_calendar_auth.py.",
            operation="update_event",
            retryable=False,
            provider=error.provider,
        ) from None
    except EventUpdateUnconfirmedError:
        raise ServiceError(
            ErrorCode.PROVIDER_ERROR,
            "Google Calendar update could not be confirmed. "
            "Check the calendar before retrying.",
            operation="update_event",
            retryable=False,
            provider=True,
        ) from None


@app.delete("/events/{event_id}", status_code=204)
def delete_event(
    event_id: str,
    deleter: Annotated[EventDeleter, Depends(get_event_deleter)],
) -> Response:
    """Delete an event; repeating the request returns 404."""
    if not EVENT_ID_PATTERN.fullmatch(event_id):
        raise ServiceError(
            ErrorCode.INVALID_INPUT,
            "Event ID must be 1-1024 letters, digits, '_' or '-'.",
            operation="delete_event",
            retryable=False,
            provider=False,
        )
    try:
        deleter.delete_event(event_id)
    except EventDeletionNotFoundError:
        raise ServiceError(
            ErrorCode.NOT_FOUND,
            "Event not found.",
            operation="delete_event",
            retryable=False,
            provider=True,
        ) from None
    except EventDeletionDeniedError:
        raise ServiceError(
            ErrorCode.ACCESS_DENIED,
            "Google Calendar denied access to this event.",
            operation="delete_event",
            retryable=False,
            provider=True,
        ) from None
    except EventDeletionUnavailableError:
        raise ServiceError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "Google Calendar authorization is unavailable. "
            "Run scripts/google_calendar_auth.py.",
            operation="delete_event",
            retryable=False,
            provider=False,
        ) from None
    except EventDeletionUnconfirmedError:
        raise ServiceError(
            ErrorCode.PROVIDER_ERROR,
            "Google Calendar deletion could not be confirmed. "
            "Retrying is safe; it returns not_found if the event is already gone.",
            operation="delete_event",
            retryable=True,
            provider=True,
        ) from None
    return Response(status_code=204)
