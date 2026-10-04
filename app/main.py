from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException

from app.models import Event

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
