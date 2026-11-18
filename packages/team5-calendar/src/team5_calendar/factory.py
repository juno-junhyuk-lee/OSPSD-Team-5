"""Create the existing Google implementation without a web framework."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from calendar_contract import (
    CalendarError,
    CalendarService,
    CreateEvent,
    ErrorCode,
    Event,
    ReplaceEvent,
)

from .authorization import TokenAuthorization, active_authorization
from .calendar_service import GoogleCalendarService
from .google_create_events import GoogleEventCreator
from .google_delete_events import GoogleEventDeleter
from .google_events import GoogleEventReader
from .google_update_events import GoogleEventUpdater


class _ConfiguredCalendarService(GoogleCalendarService):
    def __init__(self, token_file: str | Path) -> None:
        super().__init__(
            creator=GoogleEventCreator(),
            reader=GoogleEventReader(),
            updater=GoogleEventUpdater(),
            deleter=GoogleEventDeleter(),
        )
        self._authorization = TokenAuthorization(token_file)

    @contextmanager
    def _configured(self) -> Iterator[None]:
        token = active_authorization.set(self._authorization)
        try:
            yield
        except CalendarError as error:
            if error.code == ErrorCode.PROVIDER_UNAVAILABLE and not error.retryable:
                raise CalendarError(
                    error.code,
                    "Calendar authorization is unavailable. Run python -m "
                    "team5_calendar.authorize with your OAuth client and token file.",
                    retryable=False,
                    details=error.details,
                ) from None
            raise
        finally:
            active_authorization.reset(token)

    def create(self, request: CreateEvent) -> Event:
        with self._configured():
            return super().create(request)

    def get(self, event_id: str) -> Event:
        with self._configured():
            return super().get(event_id)

    def replace(self, event_id: str, request: ReplaceEvent) -> Event:
        with self._configured():
            return super().replace(event_id, request)

    def delete(self, event_id: str) -> None:
        with self._configured():
            super().delete(event_id)


def create_calendar_service(*, token_file: str | Path) -> CalendarService:
    """Bind one external OAuth token file; authorize lazily on the first call."""
    return _ConfiguredCalendarService(token_file)
