from json import JSONDecodeError
from pathlib import Path

from google.auth.exceptions import GoogleAuthError, TransportError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build  # type: ignore[import-untyped]
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from httplib2 import HttpLib2Error  # type: ignore[import-untyped]
from requests.exceptions import RequestException

from app.calendar_provider import (
    CalendarMetadataAccessDeniedError,
    CalendarMetadataAuthenticationError,
    CalendarMetadataNotFoundError,
    CalendarMetadataProviderError,
    CalendarMetadataUnavailableError,
)
from app.models import Calendar

TOKEN_PATH = Path(__file__).resolve().parents[1] / "token.json"
RATE_LIMIT_REASONS = {"rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded"}
TEMPORARY_HTTP_STATUSES = {408, 429, 500, 502, 503, 504}


class GoogleCalendarReader:
    def get_primary_calendar(self) -> Calendar:
        """Read Google metadata and translate it into the public calendar model."""
        try:
            credentials = Credentials.from_authorized_user_file(str(TOKEN_PATH))
        except (OSError, ValueError, GoogleAuthError) as error:
            raise CalendarMetadataAuthenticationError from error
        try:
            with build("calendar", "v3", credentials=credentials) as service:
                data = (
                    service.calendars().get(calendarId="primary").execute(num_retries=0)
                )
        except HttpError as error:
            if error.resp.status == 404:
                raise CalendarMetadataNotFoundError from error
            if error.resp.status == 401:
                raise CalendarMetadataAuthenticationError(provider=True) from error
            # Google also reports quota limits as 403.
            details = error.error_details
            rate_limited = isinstance(details, list) and any(
                isinstance(detail, dict)
                and isinstance(detail.get("reason"), str)
                and detail["reason"] in RATE_LIMIT_REASONS
                for detail in details
            )
            if error.resp.status in TEMPORARY_HTTP_STATUSES or (
                error.resp.status == 403 and rate_limited
            ):
                raise CalendarMetadataUnavailableError from error
            if error.resp.status == 403:
                raise CalendarMetadataAccessDeniedError from error
            raise CalendarMetadataProviderError from error
        except (TransportError, HttpLib2Error, RequestException, OSError) as error:
            raise CalendarMetadataUnavailableError from error
        except GoogleAuthError as error:
            raise CalendarMetadataAuthenticationError(provider=True) from error
        except JSONDecodeError as error:
            raise CalendarMetadataProviderError from error

        if not isinstance(data, dict):
            raise CalendarMetadataProviderError
        title = data.get("summary")
        time_zone = data.get("timeZone")
        if not isinstance(title, str) or not isinstance(time_zone, str):
            raise CalendarMetadataProviderError
        return Calendar(id="primary", title=title, time_zone=time_zone)
