"""Provider-independent contract for creating timed events."""

from typing import Protocol

from app.models import CreateEventRequest, Event


class EventCreationUnavailableError(Exception):
    """Local authorization is unavailable; no provider write was attempted."""


class EventCreationUnconfirmedError(Exception):
    """Creation could not be confirmed; the provider may have accepted the write."""


class EventCreator(Protocol):
    """Create timed events in the configured calendar."""

    def create_event(self, request: CreateEventRequest) -> Event:
        """Create one new event from validated, normalized input.

        Return the generated id, normalized title, and the supplied time instants.
        Each successful call creates a distinct event; creation is not idempotent.
        Raise EventCreationUnavailableError before a write if authorization is
        unusable, or EventCreationUnconfirmedError when the result is uncertain.
        Do not automatically retry an uncertain write.
        """
        ...
