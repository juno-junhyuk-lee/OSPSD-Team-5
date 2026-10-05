from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from app.google_auth import CalendarAuthenticationError
from app.google_events import (
    CalendarProviderError,
    EventNotFoundError,
    UnsupportedEventError,
    retrieve_event,
)
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
    """Create a timed event in local memory and return its generated ID."""
    event_id = uuid4().hex
    while event_id in LOCAL_EVENTS:
        event_id = uuid4().hex
    event = Event(
        id=event_id,
        title=request.title,
        start_time=request.start_time,
        end_time=request.end_time,
    )
    LOCAL_EVENTS[event_id] = event
    return event
