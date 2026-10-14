from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Response

from app.calendar_dependencies import get_calendar_reader
from app.calendar_provider import CalendarReader
from app.event_creation_dependencies import get_event_creator
from app.event_creation_provider import (
    EventCreationUnavailableError,
    EventCreationUnconfirmedError,
    EventCreator,
)
from app.event_deletion_provider import (
    EventDeleter,
    EventDeletionNotFoundError,
    EventDeletionUnavailableError,
    EventDeletionUnconfirmedError,
)
from app.event_dependencies import get_event_reader
from app.event_provider import (
    CalendarAuthenticationError,
    CalendarProviderError,
    EventNotFoundError,
    EventReader,
    UnsupportedEventError,
)
from app.event_update_dependencies import get_event_updater
from app.event_update_provider import (
    EventUpdateNotFoundError,
    EventUpdater,
    EventUpdateUnavailableError,
    EventUpdateUnconfirmedError,
)
from app.google_delete_events import GoogleEventDeleter
from app.models import Calendar, CreateEventRequest, Event, UpdateEventRequest

app = FastAPI(title="Calendar Service")

# DELETE retains fixed provider selection until Level 4 introduces injection.
event_deleter: EventDeleter = GoogleEventDeleter()


@app.get("/calendars/{calendar_id}", response_model=Calendar)
def get_calendar(
    calendar_id: str,
    reader: Annotated[CalendarReader, Depends(get_calendar_reader)],
) -> Calendar:
    """Retrieve the authenticated user's primary calendar metadata."""
    if calendar_id != "primary":
        raise HTTPException(status_code=404, detail="Calendar not found")
    try:
        return reader.get_primary_calendar()
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=503, detail="Google authorization unavailable"
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=502, detail="Calendar provider unavailable"
        ) from error


@app.get("/events/{event_id}", response_model=Event)
def get_event(
    event_id: str,
    reader: Annotated[EventReader, Depends(get_event_reader)],
) -> Event:
    """Retrieve one timed event from the authenticated primary Google Calendar."""
    try:
        return reader.get_event(event_id)
    except EventNotFoundError as error:
        raise HTTPException(status_code=404, detail="Event not found") from error
    except CalendarAuthenticationError as error:
        raise HTTPException(
            status_code=503, detail="Calendar authentication required"
        ) from error
    except UnsupportedEventError as error:
        raise HTTPException(
            status_code=422, detail="Only timed events are supported"
        ) from error
    except CalendarProviderError as error:
        raise HTTPException(
            status_code=502, detail="Calendar provider request failed"
        ) from error


@app.post("/events", response_model=Event, status_code=201)
def create_event(
    request: CreateEventRequest,
    creator: Annotated[EventCreator, Depends(get_event_creator)],
) -> Event:
    """Create a timed Google event and return its provider-assigned ID."""
    try:
        event = creator.create_event(request)
    except EventCreationUnavailableError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Google Calendar authorization is unavailable. "
                "Run scripts/google_calendar_auth.py."
            ),
        ) from None
    except EventCreationUnconfirmedError:
        raise HTTPException(
            status_code=502,
            detail=(
                "Google Calendar creation could not be confirmed. "
                "Check the calendar before retrying."
            ),
        ) from None
    return event


@app.patch("/events/{event_id}", response_model=Event)
def update_event(
    event_id: str,
    request: UpdateEventRequest,
    updater: Annotated[EventUpdater, Depends(get_event_updater)],
) -> Event:
    """Update a timed Google event and return the refreshed Event fields."""
    try:
        return updater.update_event(event_id, request)
    except EventUpdateNotFoundError:
        raise HTTPException(status_code=404, detail="Event not found") from None
    except EventUpdateUnavailableError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Google Calendar authorization is unavailable. "
                "Run scripts/google_calendar_auth.py."
            ),
        ) from None
    except EventUpdateUnconfirmedError:
        raise HTTPException(
            status_code=502,
            detail=(
                "Google Calendar update could not be confirmed. "
                "Check the calendar before retrying."
            ),
        ) from None


@app.delete("/events/{event_id}", status_code=204)
def delete_event(event_id: str) -> Response:
    """Delete an event; repeating the request returns 404."""
    try:
        event_deleter.delete_event(event_id)
    except EventDeletionNotFoundError:
        raise HTTPException(status_code=404, detail="Event not found") from None
    except EventDeletionUnavailableError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Google Calendar authorization is unavailable. "
                "Run scripts/google_calendar_auth.py."
            ),
        ) from None
    except EventDeletionUnconfirmedError:
        raise HTTPException(
            status_code=502,
            detail=(
                "Google Calendar deletion could not be confirmed. "
                "Retrying is safe; it returns 404 if the event is already gone."
            ),
        ) from None
    return Response(status_code=204)
