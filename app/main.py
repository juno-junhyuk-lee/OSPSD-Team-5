from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from google.auth.exceptions import TransportError
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from httplib2 import HttpLib2Error  # type: ignore[import-untyped]
from pydantic import ValidationError
from requests.exceptions import RequestException

from app.google_calendar import GoogleCalendarSetupError, create_google_event
from app.models import Calendar, CreateEventRequest, Event

app = FastAPI(title="Calendar Service")

LOCAL_CALENDARS: dict[str, Calendar] = {
    "primary": Calendar(
        id="primary", title="Team 5 Calendar", time_zone="America/New_York"
    )
}

LOCAL_EVENTS: dict[str, Event] = {
    "test-event": Event(
        id="test-event",
        title="Example Event",
        start_time=datetime(2026, 10, 5, 18, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 5, 19, 0, tzinfo=timezone.utc),
    )
}


@app.get("/calendars/{calendar_id}", response_model=Calendar)
def get_calendar(calendar_id: str) -> Calendar:
    """Retrieve calendar metadata without changing state."""
    calendar = LOCAL_CALENDARS.get(calendar_id)
    if calendar is None:
        raise HTTPException(status_code=404, detail="Calendar not found")
    return calendar


@app.get("/events/{event_id}", response_model=Event)
def get_event(event_id: str) -> Event:
    """Retrieve one local calendar event by its ID without changing state."""
    event = LOCAL_EVENTS.get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.post("/events", response_model=Event, status_code=201)
def create_event(request: CreateEventRequest) -> Event:
    """Create a Google event and mirror it for the current local GET route."""
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
    LOCAL_EVENTS[event.id] = event
    return event
