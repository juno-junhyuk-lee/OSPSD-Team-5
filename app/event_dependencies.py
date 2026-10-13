from app.event_deletion_provider import EventDeleter
from app.event_provider import EventReader
from app.google_delete_events import GoogleEventDeleter
from app.google_events import GoogleEventReader


def get_event_reader() -> EventReader:
    """Supply the event provider for normal requests."""
    return GoogleEventReader()


def get_event_deleter() -> EventDeleter:
    """Supply the event deletion provider for normal requests."""
    return GoogleEventDeleter()
