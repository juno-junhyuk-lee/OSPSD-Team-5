"""Provider-independent contract for creating timed events."""

from typing import Protocol

from app.models import CreateEventRequest, Event


class EventCreationUnavailableError(Exception):
    """Authorization is unavailable or rejected; creation was not authorized."""

    def __init__(self, message: str = "", *, provider: bool = False) -> None:
        super().__init__(message)
        self.provider = provider


class EventCreationDeniedError(Exception):
    """The provider refused permission to create the event."""


class EventCreationUnconfirmedError(Exception):
    """Creation could not be confirmed; the provider may have accepted the write."""


class EventCreator(Protocol):
    """Create timed events in the configured calendar."""

    def create_event(self, request: CreateEventRequest) -> Event:
        """Create one new event from validated, normalized input.

        Return the generated id, normalized title, and the supplied time instants.
        Each successful call creates a distinct event; creation is not idempotent.
        Raise EventCreationUnavailableError if authorization is unusable or
        rejected; its provider flag records remote authorization involvement.
        Raise EventCreationDeniedError when the provider refuses permission,
        or EventCreationUnconfirmedError when the result is uncertain.
        Do not automatically retry an uncertain write.
        """
        ...
