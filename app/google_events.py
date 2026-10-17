"""Translate Google events to the public timed-event model."""

from collections.abc import Mapping
from contextlib import closing

from google.auth.exceptions import TransportError
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from httplib2 import HttpLib2Error  # type: ignore[import-untyped]
from pydantic import ValidationError
from requests.exceptions import RequestException

from app.event_provider import (
    CalendarAuthenticationError,
    CalendarProviderError,
    EventAccessDeniedError,
    EventNotFoundError,
    EventReadUnavailableError,
    UnsupportedEventError,
)
from app.google_auth import calendar_client
from app.models import Event

# Google can report quota/rate limits as 403 instead of 429.
RATE_LIMIT_REASONS = {"rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded"}
TEMPORARY_HTTP_STATUSES = {408, 429, 500, 502, 503, 504}


def is_rate_limited(error: HttpError) -> bool:
    """Recognize Google's structured limit reasons without using error text."""
    details = error.error_details
    return isinstance(details, list) and any(
        isinstance(detail, dict)
        and isinstance(detail.get("reason"), str)
        and detail["reason"] in RATE_LIMIT_REASONS
        for detail in details
    )


def translate_event(data: Mapping[str, object]) -> Event:
    start = data.get("start")
    end = data.get("end")
    if not isinstance(start, dict) or not isinstance(end, dict):
        raise CalendarProviderError
    if "dateTime" not in start or "dateTime" not in end:
        if "date" in start or "date" in end:
            raise UnsupportedEventError
        raise CalendarProviderError
    # Google permits untitled events; preserve them as an empty title.
    try:
        return Event.model_validate(
            {
                "id": data.get("id"),
                "title": data.get("summary", ""),
                "start_time": start["dateTime"],
                "end_time": end["dateTime"],
            }
        )
    except ValidationError as error:
        raise CalendarProviderError from error


class GoogleEventReader:
    """Read Google events through the service event contract."""

    def get_event(self, event_id: str) -> Event:
        try:
            with closing(calendar_client()) as service:
                data = (
                    service.events()
                    .get(calendarId="primary", eventId=event_id)
                    .execute()
                )
        except HttpError as error:
            if error.resp.status == 404:
                raise EventNotFoundError from error
            if error.resp.status == 401:
                raise CalendarAuthenticationError from error
            if error.resp.status in TEMPORARY_HTTP_STATUSES or (
                error.resp.status == 403 and is_rate_limited(error)
            ):
                raise EventReadUnavailableError from error
            if error.resp.status == 403:
                raise EventAccessDeniedError from error
            raise CalendarProviderError from error
        except (TransportError, HttpLib2Error, RequestException, OSError) as error:
            raise EventReadUnavailableError from error
        if not isinstance(data, dict):
            raise CalendarProviderError
        return translate_event(data)
