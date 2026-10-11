from app.calendar_provider import CalendarReader
from app.google_calendar import GoogleCalendarReader


def get_calendar_reader() -> CalendarReader:
    """Supply the calendar provider for normal requests."""
    # Tests override this dependency without constructing Google clients.
    return GoogleCalendarReader()
