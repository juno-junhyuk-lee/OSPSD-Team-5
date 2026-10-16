"""Provider-independent contract for deleting events."""

from typing import Protocol


class EventDeletionNotFoundError(Exception):
    """No event has this ID, or it was already deleted."""


class EventDeletionDeniedError(Exception):
    """The provider refused the deletion; the event was not deleted."""


class EventDeletionUnavailableError(Exception):
    """Local authorization is unavailable; no provider call was attempted."""


class EventDeletionUnconfirmedError(Exception):
    """Deletion could not be confirmed; the provider may have deleted the event."""


class EventDeleter(Protocol):
    """Delete events from the configured calendar."""

    def delete_event(self, event_id: str) -> None:
        """Delete one event by provider-assigned ID without notifying attendees.

        Return nothing on success. Only the identified event changes. Raise
        EventDeletionNotFoundError when no event has the ID, including one that
        was already deleted, so a repeated call reports it as missing. Raise
        EventDeletionDeniedError when the provider refuses access. Raise
        EventDeletionUnavailableError before a provider call if authorization is
        unusable, or EventDeletionUnconfirmedError when the result is uncertain.
        Do not automatically retry; a caller's retry is safe and reports a
        completed deletion as missing.
        """
        ...
