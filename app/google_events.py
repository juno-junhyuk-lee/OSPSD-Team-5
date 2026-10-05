"""Translate Google events to the public timed-event model."""

from collections.abc import Mapping

from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from pydantic import ValidationError

from app.google_auth import calendar_client
from app.models import Event


class EventNotFoundError(Exception):
    pass


class CalendarProviderError(Exception):
    pass


class UnsupportedEventError(Exception):
    pass


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


def retrieve_event(event_id: str) -> Event:
    try:
        data = (
            calendar_client()
            .events()
            .get(calendarId="primary", eventId=event_id)
            .execute()
        )
    except HttpError as error:
        if error.resp.status == 404:
            raise EventNotFoundError from error
        raise CalendarProviderError from error
    except OSError as error:
        raise CalendarProviderError from error
    if not isinstance(data, dict):
        raise CalendarProviderError
    return translate_event(data)
