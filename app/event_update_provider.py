"""Provider-independent contract for updating timed events."""

from typing import Protocol

from calendar_contract import Event, ReplaceEvent


class EventUpdateNotFoundError(Exception):
    """The event is missing, already deleted, or cancelled."""


class EventUpdateDeniedError(Exception):
    """The provider refused the update; the event was not changed."""


class EventUpdateUnavailableError(Exception):
    """Authorization is unavailable or rejected; no authorized write occurred."""

    def __init__(self, message: str = "", *, provider: bool = False) -> None:
        super().__init__(message)
        self.provider = provider


class EventUpdateUnconfirmedError(Exception):
    """Update could not be confirmed; the provider may have accepted the write."""


class EventUpdateProviderUnavailableError(Exception):
    """A temporary failure prevented or explicitly rejected the write."""


class EventUpdateProviderError(Exception):
    """The provider returned an unexpected update response."""


class EventUpdateUnsupportedError(Exception):
    """Replacing this event shape is unsupported; no write occurred."""


class EventUpdater(Protocol):
    """Update timed events in the configured calendar."""

    def update_event(self, event_id: str, request: ReplaceEvent) -> Event:
        """Replace title and times for one existing timed event.

        Return the same id with the refreshed title and start/end instants.
        Raise EventUpdateNotFoundError when the event is absent or cancelled,
        EventUpdateDeniedError when the provider refuses access,
        EventUpdateUnsupportedError before writing an all-day event or series,
        EventUpdateUnavailableError if authorization is unusable or rejected
        (provider flag records remote authorization involvement), or
        EventUpdateUnconfirmedError when the result is uncertain.
        Do not automatically retry an uncertain write.
        """
        ...
