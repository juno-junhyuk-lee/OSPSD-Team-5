from app.event_deletion_provider import EventDeleter
from app.google_delete_events import GoogleEventDeleter


def get_event_deleter() -> EventDeleter:
    """Supply the event deletion provider for normal requests."""
    return GoogleEventDeleter()
