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
    EventUpdateProviderError,
    EventUpdateProviderUnavailableError,
    EventUpdateUnavailableError,
    EventUpdateUnconfirmedError,
    EventUpdateUnsupportedError,
)
from app.google_create_events import GoogleCalendarSetupError, load_credentials
from app.google_delete_events import GoogleEventNotFoundError, is_permission_denied
from app.google_events import TEMPORARY_HTTP_STATUSES, is_rate_limited
from app.tracing import google_call


class _GoogleEventTime(BaseModel):
    dateTime: str


class _GoogleEvent(BaseModel):
    id: str = Field(min_length=1)
    summary: str
    start: _GoogleEventTime
    end: _GoogleEventTime


def update_google_event(event_id: str, request: ReplaceEvent) -> Event:
    """Patch one timed event on primary and return the public Event model."""
    body = {
        "summary": request.title.strip(),
        "start": {"dateTime": request.start},
        "end": {"dateTime": request.end},
    }
    write_started = False
    try:
        credentials = load_credentials()
        with build("calendar", "v3", credentials=credentials) as service:
            with google_call("events.get"):
                existing = (
                    service.events()
                    .get(calendarId="primary", eventId=event_id)
                    .execute(num_retries=0)
                )
            if not isinstance(existing, dict):
                raise EventUpdateProviderError
            if existing.get("status") == "cancelled":
                raise GoogleEventNotFoundError(event_id)
            start, end = existing.get("start"), existing.get("end")
            if not isinstance(start, dict) or not isinstance(end, dict):
                raise EventUpdateProviderError
            if "date" in start or "date" in end or existing.get("recurrence"):
                raise EventUpdateUnsupportedError
            if not isinstance(start.get("dateTime"), str) or not isinstance(
                end.get("dateTime"), str
            ):
                raise EventUpdateProviderError
            patch = service.events().patch(
                calendarId="primary", eventId=event_id, body=body
            )
            write_started = True
            with google_call("events.patch"):
                result = patch.execute(num_retries=0)
    except HttpError as error:
        if error.resp.status in (404, 410):
            raise GoogleEventNotFoundError(event_id) from error
        if not write_started and (
            error.resp.status in TEMPORARY_HTTP_STATUSES
            or (error.resp.status == 403 and is_rate_limited(error))
        ):
            raise EventUpdateProviderUnavailableError from error
        raise
    except (TransportError, HttpLib2Error, RequestException, OSError) as error:
        if not write_started:
            raise EventUpdateProviderUnavailableError from error
        raise
    if not isinstance(result, dict):
        raise EventUpdateProviderError
    if result.get("status") == "cancelled":
        raise GoogleEventNotFoundError(event_id)
    provider_event = _GoogleEvent.model_validate(result)
    if provider_event.id != event_id:
        raise EventUpdateProviderError
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
            if error.resp.status == 429 or (
                error.resp.status == 403 and is_rate_limited(error)
            ):
                raise EventUpdateProviderUnavailableError from error
            raise EventUpdateUnconfirmedError from error
        except (
            TransportError,
            HttpLib2Error,
            RequestException,
            OSError,
            ValidationError,
        ) as error:
            raise EventUpdateUnconfirmedError from error
