"""Provider-independent contract for reading timed events."""

from typing import Protocol

from app.models import Event


class EventNotFoundError(Exception):
    """The requested event does not exist."""


class CalendarProviderError(Exception):
    """The provider request failed or returned invalid event data."""


class EventAccessDeniedError(CalendarProviderError):
    """The provider refused permission to read the event."""


class EventReadUnavailableError(CalendarProviderError):
    """A temporary provider or transport failure prevented the read."""


class UnsupportedEventError(Exception):
    """The event cannot be represented by the timed-event model."""


class CalendarAuthenticationError(Exception):
    """Authorization is unavailable, rejected, or requires renewal."""


class EventReader(Protocol):
    """Read timed events from the authorized calendar."""

    def get_event(self, event_id: str) -> Event:
        """Return one event by provider-assigned ID without changing events.

        Return id, title, start_time, and end_time; an absent title is empty.
        Raise EventNotFoundError for a missing event, UnsupportedEventError
        for an all-day event, CalendarAuthenticationError for unavailable
        or rejected authorization, EventAccessDeniedError for denied access,
        EventReadUnavailableError for a temporary provider/transport failure,
        or CalendarProviderError for other failed requests or invalid data.
        The access and temporary errors specialize CalendarProviderError so
        existing callers can still handle provider failures together.
        """
        ...
