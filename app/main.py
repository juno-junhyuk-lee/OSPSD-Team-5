from fastapi import FastAPI, HTTPException, Response
from google.auth.exceptions import TransportError
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from httplib2 import HttpLib2Error  # type: ignore[import-untyped]
from pydantic import ValidationError
from requests.exceptions import RequestException

from app.google_auth import CalendarAuthenticationError
from app.google_calendar import get_primary_calendar
from app.google_create_events import GoogleCalendarSetupError, create_google_event
from app.google_delete_events import GoogleEventNotFoundError, delete_google_event
from app.google_events import (
    CalendarProviderError,
    EventNotFoundError,
    UnsupportedEventError,
    retrieve_event,
)
from app.models import Calendar, CreateEventRequest, Event

app = FastAPI(title="Calendar Service")


@app.get("/calendars/{calendar_id}", response_model=Calendar)
def get_calendar(calendar_id: str) -> Calendar:
    """Retrieve the authenticated user's primary calendar metadata."""
    if calendar_id != "primary":
        raise HTTPException(status_code=404, detail="Calendar not found")
    try:
        return get_primary_calendar()
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=503, detail="Google authorization unavailable"
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=502, detail="Calendar provider unavailable"
        ) from error


@app.get("/events/{event_id}", response_model=Event)
def get_event(event_id: str) -> Event:
    """Retrieve one timed event from the authenticated primary Google Calendar."""
    try:
        return retrieve_event(event_id)
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
def create_event(request: CreateEventRequest) -> Event:
    """Create a timed Google event and return its provider-assigned ID."""
    try:
        event = create_google_event(request)
    except GoogleCalendarSetupError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Google Calendar authorization is unavailable. "
                "Run scripts/google_calendar_auth.py."
            ),
        ) from None
    except (
        HttpError,
        TransportError,
        HttpLib2Error,
        RequestException,
        OSError,
        ValidationError,
    ):
        raise HTTPException(
            status_code=502,
            detail=(
                "Google Calendar creation could not be confirmed. "
                "Check the calendar before retrying."
            ),
        ) from None
    return event


@app.delete("/events/{event_id}", status_code=204)
def delete_event(event_id: str) -> Response:
    """Delete a Google event; repeating the request returns 404."""
    try:
        delete_google_event(event_id)
    except GoogleEventNotFoundError:
        raise HTTPException(status_code=404, detail="Event not found") from None
    except GoogleCalendarSetupError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Google Calendar authorization is unavailable. "
                "Run scripts/google_calendar_auth.py."
            ),
        ) from None
    except HttpError, TransportError, HttpLib2Error, RequestException, OSError:
        raise HTTPException(
            status_code=502,
            detail=(
                "Google Calendar deletion could not be confirmed. "
                "Retrying is safe; it returns 404 if the event is already gone."
            ),
        ) from None
    return Response(status_code=204)
