from typing import Protocol

from app.models import Calendar


class CalendarReader(Protocol):
    """Read calendar metadata without exposing provider details."""

    def get_primary_calendar(self) -> Calendar:
        """Return primary metadata without changing external state."""
        ...
