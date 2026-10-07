"""Update timed events using the team's local Google authorization."""

from googleapiclient.discovery import build  # type: ignore[import-untyped]
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from pydantic import AwareDatetime, BaseModel, Field

from app.google_create_events import load_credentials
from app.google_delete_events import GoogleEventNotFoundError
from app.models import Event, UpdateEventRequest


class _GoogleEventTime(BaseModel):
    dateTime: AwareDatetime


class _GoogleEvent(BaseModel):
    id: str = Field(min_length=1)
    summary: str
    start: _GoogleEventTime
    end: _GoogleEventTime


def update_google_event(event_id: str, request: UpdateEventRequest) -> Event:
    """Patch one timed event on primary and return the public Event model."""
    credentials = load_credentials()
    body = {
        "summary": request.title,
        "start": {"dateTime": request.start_time.isoformat()},
        "end": {"dateTime": request.end_time.isoformat()},
    }
    try:
        with build("calendar", "v3", credentials=credentials) as service:
            result = (
                service.events()
                .patch(calendarId="primary", eventId=event_id, body=body)
                .execute(num_retries=0)
            )
    except HttpError as error:
        if error.resp.status in (404, 410):
            raise GoogleEventNotFoundError(event_id) from error
        raise
    # Google may still patch a deleted event and return status "cancelled".
    if result.get("status") == "cancelled":
        raise GoogleEventNotFoundError(event_id)
    provider_event = _GoogleEvent.model_validate(result)
    translated = UpdateEventRequest.model_validate(
        {
            "title": provider_event.summary,
            "start_time": provider_event.start.dateTime.isoformat(),
            "end_time": provider_event.end.dateTime.isoformat(),
        }
    )
    return Event(
        id=provider_event.id,
        title=translated.title,
        start_time=translated.start_time,
        end_time=translated.end_time,
    )
