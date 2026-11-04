"""Implement the shared Calendar interface using Team 5's Google adapters."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal

from calendar_contract import CalendarError, CreateEvent, ErrorCode, Event, ReplaceEvent

from app.event_creation_provider import (
    EventCreationDeniedError,
    EventCreationProviderUnavailableError,
    EventCreationUnavailableError,
    EventCreationUnconfirmedError,
    EventCreator,
)
from app.event_deletion_provider import (
    EventDeleter,
    EventDeletionDeniedError,
    EventDeletionNotFoundError,
    EventDeletionProviderUnavailableError,
    EventDeletionUnavailableError,
    EventDeletionUnconfirmedError,
)
from app.event_provider import (
    CalendarAuthenticationError,
    CalendarProviderError,
    EventAccessDeniedError,
    EventNotFoundError,
    EventReader,
    EventReadUnavailableError,
    UnsupportedEventError,
)
from app.event_update_provider import (
    EventUpdateDeniedError,
    EventUpdateNotFoundError,
    EventUpdateProviderError,
    EventUpdateProviderUnavailableError,
    EventUpdater,
    EventUpdateUnavailableError,
    EventUpdateUnconfirmedError,
)

Operation = Literal["create", "get", "replace", "delete"]


class GoogleCalendarService:
    """Compose existing operations and expose only shared Calendar failures."""

    def __init__(
        self,
        *,
        creator: EventCreator,
        reader: EventReader,
        updater: EventUpdater,
        deleter: EventDeleter,
    ) -> None:
        self.creator = creator
        self.reader = reader
        self.updater = updater
        self.deleter = deleter

    def create(self, request: CreateEvent) -> Event:
        with self._errors("create"):
            return self.creator.create_event(request)

    def get(self, event_id: str) -> Event:
        with self._errors("get"):
            return self.reader.get_event(event_id)

    def replace(self, event_id: str, request: ReplaceEvent) -> Event:
        with self._errors("replace"):
            return self.updater.update_event(event_id, request)

    def delete(self, event_id: str) -> None:
        with self._errors("delete"):
            self.deleter.delete_event(event_id)

    @staticmethod
    def _error(
        code: ErrorCode, message: str, *, retryable: bool = False, provider: bool = True
    ) -> CalendarError:
        # This flag is safe log context, not raw provider exception details.
        return CalendarError(code, message, retryable, details={"provider": provider})

    @contextmanager
    def _errors(self, operation: Operation) -> Iterator[None]:
        try:
            yield
        except EventNotFoundError, EventUpdateNotFoundError, EventDeletionNotFoundError:
            raise self._error(ErrorCode.NOT_FOUND, "Event not found.") from None
        except (
            CalendarAuthenticationError,
            EventCreationUnavailableError,
            EventUpdateUnavailableError,
            EventDeletionUnavailableError,
        ) as error:
            message = (
                "Calendar authentication required. Run scripts/google_calendar_auth.py."
                if operation == "get"
                else "Google Calendar authorization is unavailable. "
                "Run scripts/google_calendar_auth.py."
            )
            raise self._error(
                ErrorCode.PROVIDER_UNAVAILABLE, message, provider=error.provider
            ) from None
        except (
            EventAccessDeniedError,
            EventCreationDeniedError,
            EventUpdateDeniedError,
            EventDeletionDeniedError,
        ):
            messages = {
                "get": "Calendar denied access to this event.",
                "create": "Google Calendar denied permission to create this event.",
                "replace": "Google Calendar denied permission to update this event.",
                "delete": "Google Calendar denied access to this event.",
            }
            raise self._error(ErrorCode.ACCESS_DENIED, messages[operation]) from None
        except (
            EventReadUnavailableError,
            EventCreationProviderUnavailableError,
            EventUpdateProviderUnavailableError,
            EventDeletionProviderUnavailableError,
        ):
            raise self._error(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "Calendar provider temporarily unavailable. Retry later.",
                retryable=True,
            ) from None
        except (
            EventCreationUnconfirmedError,
            EventUpdateUnconfirmedError,
            EventDeletionUnconfirmedError,
        ):
            messages = {
                "create": "Google Calendar creation could not be confirmed. "
                "Check the calendar before retrying.",
                "replace": "Google Calendar update could not be confirmed. "
                "Check the calendar before retrying.",
                "delete": "Google Calendar deletion could not be confirmed. "
                "Retrying is safe; it returns not_found if the event is already gone.",
            }
            raise self._error(
                ErrorCode.PROVIDER_ERROR,
                messages[operation],
                retryable=operation == "delete",
            ) from None
        except UnsupportedEventError:
            raise self._error(
                ErrorCode.INVALID_INPUT, "Only timed events are supported."
            ) from None
        except CalendarProviderError, EventUpdateProviderError:
            raise self._error(
                ErrorCode.PROVIDER_ERROR, "Calendar provider request failed."
            ) from None
