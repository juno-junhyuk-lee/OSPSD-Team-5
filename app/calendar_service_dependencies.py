"""Select the shared service while keeping operation providers replaceable."""

from typing import Annotated

from calendar_contract import CalendarService
from fastapi import Depends

from app.calendar_service import GoogleCalendarService
from app.event_creation_dependencies import get_event_creator
from app.event_creation_provider import EventCreator
from app.event_deletion_dependencies import get_event_deleter
from app.event_deletion_provider import EventDeleter
from app.event_dependencies import get_event_reader
from app.event_provider import EventReader
from app.event_update_dependencies import get_event_updater
from app.event_update_provider import EventUpdater


def get_calendar_service(
    creator: Annotated[EventCreator, Depends(get_event_creator)],
    reader: Annotated[EventReader, Depends(get_event_reader)],
    updater: Annotated[EventUpdater, Depends(get_event_updater)],
    deleter: Annotated[EventDeleter, Depends(get_event_deleter)],
) -> CalendarService:
    """Supply the Google implementation of the shared four-operation interface."""
    return GoogleCalendarService(
        creator=creator, reader=reader, updater=updater, deleter=deleter
    )
