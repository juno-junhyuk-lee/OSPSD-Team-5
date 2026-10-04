from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from app.models import CreateEventRequest, Event

app = FastAPI(title="Calendar Service")

LOCAL_EVENTS: dict[str, Event] = {
    "test-event": Event(
        id="test-event",
        title="Example Event",
        start_time=datetime(2026, 10, 5, 18, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 5, 19, 0, tzinfo=timezone.utc),
    )
}


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
