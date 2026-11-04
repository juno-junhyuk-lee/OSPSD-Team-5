"""Update timed events using the team's local Google authorization."""

from calendar_contract import Event, ReplaceEvent
from google.auth.exceptions import RefreshError, TransportError
from googleapiclient.discovery import build  # type: ignore[import-untyped]
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from httplib2 import HttpLib2Error  # type: ignore[import-untyped]
from pydantic import BaseModel, Field, ValidationError
from requests.exceptions import RequestException

from app.event_update_provider import (
    EventUpdateDeniedError,
    EventUpdateNotFoundError,
    EventUpdateUnavailableError,
    EventUpdateUnconfirmedError,
)
from app.google_create_events import GoogleCalendarSetupError, load_credentials
from app.google_delete_events import GoogleEventNotFoundError, is_permission_denied


class _GoogleEventTime(BaseModel):
    dateTime: str


class _GoogleEvent(BaseModel):
    id: str = Field(min_length=1)
    summary: str
    start: _GoogleEventTime
    end: _GoogleEventTime


def update_google_event(event_id: str, request: ReplaceEvent) -> Event:
    """Patch one timed event on primary and return the public Event model."""
    credentials = load_credentials()
    body = {
        "summary": request.title.strip(),
        "start": {"dateTime": request.start},
        "end": {"dateTime": request.end},
    }
    try:
        with build("calendar", "v3", credentials=credentials) as service:
            existing = (
                service.events()
                .get(calendarId="primary", eventId=event_id)
                .execute(num_retries=0)
            )
            if existing.get("status") == "cancelled":
                raise GoogleEventNotFoundError(event_id)
            result = (
                service.events()
                .patch(calendarId="primary", eventId=event_id, body=body)
                .execute(num_retries=0)
            )
    except HttpError as error:
        if error.resp.status in (404, 410):
            raise GoogleEventNotFoundError(event_id) from error
        raise
    # Guard if Google still returns a cancelled body after patch.
    if result.get("status") == "cancelled":
        raise GoogleEventNotFoundError(event_id)
    provider_event = _GoogleEvent.model_validate(result)
    translated = ReplaceEvent.model_validate(
        {
            "title": provider_event.summary,
            "start": provider_event.start.dateTime,
            "end": provider_event.end.dateTime,
        }
    )
    return Event(
        id=provider_event.id,
        title=translated.title,
        start=translated.start,
        end=translated.end,
    )


class GoogleEventUpdater:
    """Update Google events through the service update contract."""

    def update_event(self, event_id: str, request: ReplaceEvent) -> Event:
        try:
            return update_google_event(event_id, request)
        except GoogleEventNotFoundError as error:
            raise EventUpdateNotFoundError from error
        except GoogleCalendarSetupError as error:
            raise EventUpdateUnavailableError(provider=error.provider) from error
        except RefreshError as error:
            raise EventUpdateUnavailableError(provider=True) from error
        except HttpError as error:
            if error.resp.status == 401:
                raise EventUpdateUnavailableError(provider=True) from error
            if is_permission_denied(error):
                raise EventUpdateDeniedError from error
            raise EventUpdateUnconfirmedError from error
        except (
            TransportError,
            HttpLib2Error,
            RequestException,
            OSError,
            ValidationError,
        ) as error:
            raise EventUpdateUnconfirmedError from error
