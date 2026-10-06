"""Delete events using the team's local Google authorization."""

from googleapiclient.discovery import build  # type: ignore[import-untyped]
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

from app.google_create_events import load_credentials


class GoogleEventNotFoundError(LookupError):
    """Google has no event with this ID on primary, or it was already deleted."""


def delete_google_event(event_id: str) -> None:
    """Delete one event from primary without notifying attendees."""
    credentials = load_credentials()
    try:
        with build("calendar", "v3", credentials=credentials) as service:
            service.events().delete(
                calendarId="primary", eventId=event_id, sendUpdates="none"
            ).execute(num_retries=0)
    except HttpError as error:
        # Google answers 410 Gone for an event that was already deleted.
        if error.resp.status in (404, 410):
            raise GoogleEventNotFoundError(event_id) from error
        raise
