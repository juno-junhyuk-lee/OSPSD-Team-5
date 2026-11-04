"""Delete events using the team's local Google authorization."""

from google.auth.exceptions import RefreshError, TransportError
from googleapiclient.discovery import build  # type: ignore[import-untyped]
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from httplib2 import HttpLib2Error  # type: ignore[import-untyped]
from requests.exceptions import RequestException

from app.event_deletion_provider import (
    EventDeletionDeniedError,
    EventDeletionNotFoundError,
    EventDeletionProviderUnavailableError,
    EventDeletionUnavailableError,
    EventDeletionUnconfirmedError,
)
from app.google_create_events import GoogleCalendarSetupError, load_credentials
from app.google_events import TEMPORARY_HTTP_STATUSES, is_rate_limited


class GoogleEventNotFoundError(LookupError):
    """Google has no event with this ID on primary, or it was already deleted."""


# Google also answers 403 for quota limits; those are not permission denials.
RATE_LIMIT_REASONS = {"rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded"}


def is_permission_denied(error: HttpError) -> bool:
    """Return whether Google refused access rather than rate-limiting."""
    if error.resp.status != 403:
        return False
    details = error.error_details
    reasons = (
        {detail.get("reason") for detail in details if isinstance(detail, dict)}
        if isinstance(details, list)
        else set()
    )
    return not reasons & RATE_LIMIT_REASONS


def delete_google_event(event_id: str) -> None:
    """Delete one event from primary without notifying attendees."""
    write_started = False
    try:
        credentials = load_credentials()
        with build("calendar", "v3", credentials=credentials) as service:
            delete = service.events().delete(
                calendarId="primary", eventId=event_id, sendUpdates="none"
            )
            write_started = True
            delete.execute(num_retries=0)
    except HttpError as error:
        # Google answers 410 Gone for an event that was already deleted.
        if error.resp.status in (404, 410):
            raise GoogleEventNotFoundError(event_id) from error
        if not write_started and (
            error.resp.status in TEMPORARY_HTTP_STATUSES
            or (error.resp.status == 403 and is_rate_limited(error))
        ):
            raise EventDeletionProviderUnavailableError from error
        raise
    except (TransportError, HttpLib2Error, RequestException, OSError) as error:
        if not write_started:
            raise EventDeletionProviderUnavailableError from error
        raise


class GoogleEventDeleter:
    """Delete Google events through the service deletion contract."""

    def delete_event(self, event_id: str) -> None:
        try:
            delete_google_event(event_id)
        except GoogleEventNotFoundError as error:
            raise EventDeletionNotFoundError from error
        except GoogleCalendarSetupError as error:
            raise EventDeletionUnavailableError(provider=error.provider) from error
        except RefreshError as error:
            raise EventDeletionUnavailableError(provider=True) from error
        except HttpError as error:
            if error.resp.status == 401:
                raise EventDeletionUnavailableError(provider=True) from error
            if is_permission_denied(error):
                raise EventDeletionDeniedError from error
            if error.resp.status in (403, 429):
                raise EventDeletionProviderUnavailableError from error
            raise EventDeletionUnconfirmedError from error
        except (
            TransportError,
            HttpLib2Error,
            RequestException,
            OSError,
        ) as error:
            raise EventDeletionUnconfirmedError from error
