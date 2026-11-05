import re
from typing import Annotated

from calendar_contract import (
    CalendarError,
    CalendarService,
    CreateEvent,
    Event,
    ReplaceEvent,
)
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
from app.calendar_service_dependencies import get_calendar_service
from app.errors import (
    ErrorCode,
    ErrorResponse,
    ServiceError,
    calendar_error_handler,
    request_validation_handler,
    service_error_handler,
)
from app.google_auth import hosted
from app.models import Calendar
from app.runtime import lifespan, require_hosted_access

app = FastAPI(
    title="Calendar Service",
    lifespan=lifespan,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Malformed JSON or unsupported event operation",
        },
        422: {"model": ErrorResponse, "description": "Invalid request"},
    },
)
app.middleware("http")(require_hosted_access)
app.add_exception_handler(ServiceError, service_error_handler)
app.add_exception_handler(CalendarError, calendar_error_handler)
app.add_exception_handler(RequestValidationError, request_validation_handler)


@app.get("/healthz", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
def ready() -> Response:
    if hosted() and getattr(app.state, "demo_bearer", None) is None:
        return Response(status_code=503)
    return Response(status_code=204)


# Google event IDs, including recurring instances, use only these characters.
EVENT_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,1024}")
EVENT_RESPONSES: dict[int | str, dict[str, object]] = {
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    502: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


def validate_event_id(event_id: str, *, operation: str) -> None:
    """Reject unsupported IDs before calling the provider."""
    if not EVENT_ID_PATTERN.fullmatch(event_id):
        raise ServiceError(
            ErrorCode.INVALID_INPUT,
            "Event ID must be 1-1024 letters, digits, '_' or '-'.",
            operation=operation,
            retryable=False,
            provider=False,
        )


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


@app.get("/events/{event_id}", response_model=Event, responses=EVENT_RESPONSES)
def get_event(
    event_id: str,
    service: Annotated[CalendarService, Depends(get_calendar_service)],
) -> Event:
    """Retrieve one timed event from the authenticated primary Google Calendar."""
    validate_event_id(event_id, operation="get_event")
    return service.get(event_id)


@app.post("/events", response_model=Event, status_code=201, responses=EVENT_RESPONSES)
def create_event(
    request: CreateEvent,
    service: Annotated[CalendarService, Depends(get_calendar_service)],
) -> Event:
    """Create a timed Google event and return its provider-assigned ID."""
    return service.create(request)


@app.put("/events/{event_id}", response_model=Event, responses=EVENT_RESPONSES)
def replace_event(
    event_id: str,
    request: ReplaceEvent,
    service: Annotated[CalendarService, Depends(get_calendar_service)],
) -> Event:
    """Replace a timed event's title and times, keeping its other Google fields."""
    validate_event_id(event_id, operation="replace_event")
    return service.replace(event_id, request)


@app.patch("/events/{event_id}", response_model=Event, responses=EVENT_RESPONSES)
def update_event(
    event_id: str,
    request: ReplaceEvent,
    service: Annotated[CalendarService, Depends(get_calendar_service)],
) -> Event:
    """Keep the full-field PATCH extension using the shared replacement path."""
    validate_event_id(event_id, operation="update_event")
    return service.replace(event_id, request)


@app.delete("/events/{event_id}", status_code=204, responses=EVENT_RESPONSES)
def delete_event(
    event_id: str,
    service: Annotated[CalendarService, Depends(get_calendar_service)],
) -> Response:
    """Delete an event; repeating the request returns 404."""
    validate_event_id(event_id, operation="delete_event")
    service.delete(event_id)
    return Response(status_code=204)
