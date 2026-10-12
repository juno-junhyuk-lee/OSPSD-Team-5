from app.event_provider import EventReader
from app.google_events import GoogleEventReader


def get_event_reader() -> EventReader:
    """Supply the event provider for normal requests."""
    return GoogleEventReader()
