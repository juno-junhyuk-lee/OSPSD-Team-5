"""Create timed events using the team's local Google authorization."""

from pathlib import Path
from typing import cast

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build  # type: ignore[import-untyped]
from pydantic import AwareDatetime, BaseModel, Field

from app.models import CreateEventRequest, Event

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
TOKEN_PATH = Path(__file__).resolve().parents[1] / "token.json"


class GoogleCalendarSetupError(RuntimeError):
    """Local authorization needs attention before creating an event."""


class _GoogleEventTime(BaseModel):
    dateTime: AwareDatetime


class _GoogleEvent(BaseModel):
    id: str = Field(min_length=1)
    summary: str
    start: _GoogleEventTime
    end: _GoogleEventTime


def load_credentials() -> Credentials:
    """Load or refresh a local token without starting browser authorization."""
    try:
        credentials = cast(
            Credentials,
            Credentials.from_authorized_user_file(str(TOKEN_PATH)),
        )
    except (OSError, ValueError) as error:
        raise GoogleCalendarSetupError(
            "Run scripts/google_calendar_auth.py to create a usable local token."
        ) from error
    if not credentials.has_scopes(SCOPES):
        raise GoogleCalendarSetupError(
            "Run scripts/google_calendar_auth.py to grant calendar.events access."
        )
    if not credentials.valid:
        if not credentials.expired or not credentials.refresh_token:
            raise GoogleCalendarSetupError(
                "Run scripts/google_calendar_auth.py to renew local authorization."
            )
        try:
            credentials.refresh(Request())
        except RefreshError as error:
            raise GoogleCalendarSetupError(
                "Run scripts/google_calendar_auth.py to renew local authorization."
            ) from error
        if not credentials.valid or not credentials.has_scopes(SCOPES):
            raise GoogleCalendarSetupError(
                "Refreshed authorization lacks valid calendar.events access."
            )
        TOKEN_PATH.write_text(credentials.to_json(), encoding="utf-8")
    return credentials


def create_google_event(request: CreateEventRequest) -> Event:
    """Insert into primary and translate the provider result to the public model."""
    credentials = load_credentials()
    body = {
        "summary": request.title,
        "start": {"dateTime": request.start_time.isoformat()},
        "end": {"dateTime": request.end_time.isoformat()},
    }
    with build("calendar", "v3", credentials=credentials) as service:
        result = (
            service.events()
            .insert(calendarId="primary", body=body)
            .execute(num_retries=0)
        )
    provider_event = _GoogleEvent.model_validate(result)
    translated = CreateEventRequest.model_validate(
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
