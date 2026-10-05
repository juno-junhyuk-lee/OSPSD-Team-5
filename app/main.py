from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from app.google_calendar import get_primary_calendar
from app.models import Calendar, CreateEventRequest, Event

app = FastAPI(title="Calendar Service")

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
    """Retrieve one local calendar event by its ID without changing state."""
    event = LOCAL_EVENTS.get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


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
