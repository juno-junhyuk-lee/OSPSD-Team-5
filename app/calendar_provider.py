from typing import Protocol

from app.models import Calendar


class CalendarMetadataNotFoundError(Exception):
    """The primary calendar does not exist or is not visible."""


class CalendarMetadataAuthenticationError(Exception):
    """Authorization must be configured or renewed."""

    def __init__(self, *, provider: bool = False) -> None:
        super().__init__()
        self.provider = provider


class CalendarMetadataAccessDeniedError(Exception):
    """The provider refused calendar access."""


class CalendarMetadataUnavailableError(Exception):
    """A temporary failure prevented the read."""


class CalendarMetadataProviderError(Exception):
    """The provider failed or returned invalid metadata."""


class CalendarReader(Protocol):
    """Read calendar metadata without exposing provider details."""

    def get_primary_calendar(self) -> Calendar:
        """Return primary metadata without changing external state.

        Raise CalendarMetadataNotFoundError for a missing calendar,
        CalendarMetadataAuthenticationError for unusable authorization,
        CalendarMetadataAccessDeniedError for denied access,
        CalendarMetadataUnavailableError for temporary failures, or
        CalendarMetadataProviderError for other failures or invalid data.
        """
        ...
