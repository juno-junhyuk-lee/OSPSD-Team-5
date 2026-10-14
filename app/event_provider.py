"""Provider-independent contract for reading timed events."""

from typing import Protocol

from app.models import Event


class EventNotFoundError(Exception):
    """The requested event does not exist."""


class CalendarProviderError(Exception):
    """The provider request failed or returned invalid event data."""


class UnsupportedEventError(Exception):
    """The event cannot be represented by the timed-event model."""


class CalendarAuthenticationError(Exception):
    """Authorization is unavailable or requires renewal."""


class EventReader(Protocol):
    """Read timed events from the authorized calendar."""

    def get_event(self, event_id: str) -> Event:
        """Return one event by provider-assigned ID without changing events.

        Return id, title, start_time, and end_time; an absent title is empty.
        Raise EventNotFoundError for a missing event, UnsupportedEventError
        for an all-day event, CalendarAuthenticationError for unavailable
        authorization, or CalendarProviderError for a failed request or
        invalid provider data.
        """
        ...
