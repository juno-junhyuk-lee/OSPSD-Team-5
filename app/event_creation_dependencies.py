from app.event_creation_provider import EventCreator
from app.google_create_events import GoogleEventCreator


def get_event_creator() -> EventCreator:
    """Supply the event creation provider for normal requests."""
    return GoogleEventCreator()
