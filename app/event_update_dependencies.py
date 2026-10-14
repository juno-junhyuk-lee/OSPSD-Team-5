from app.event_update_provider import EventUpdater
from app.google_update_events import GoogleEventUpdater


def get_event_updater() -> EventUpdater:
    """Supply the event update provider for normal requests."""
    return GoogleEventUpdater()
