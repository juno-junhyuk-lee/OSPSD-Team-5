"""Run the shared calendar-contract conformance suite against Team 5's service."""

import os
from typing import NoReturn
from unittest.mock import MagicMock

import pytest
from calendar_contract import CalendarService, CreateEvent, ReplaceEvent
from calendar_contract.conformance import (
    CalendarServiceConformance,
    FailingServiceFactory,
    ProviderFailure,
)

from app.calendar_service import GoogleCalendarService
from app.event_creation_provider import (
    EventCreationDeniedError,
    EventCreationProviderUnavailableError,
    EventCreationUnconfirmedError,
)
from app.event_deletion_provider import (
    EventDeletionDeniedError,
    EventDeletionProviderUnavailableError,
    EventDeletionUnconfirmedError,
)
from app.event_provider import (
    CalendarProviderError,
    EventAccessDeniedError,
    EventReadUnavailableError,
)
from app.event_update_provider import (
    EventUpdateDeniedError,
    EventUpdateProviderError,
    EventUpdateProviderUnavailableError,
    EventUpdateUnconfirmedError,
)
from app.google_create_events import GoogleEventCreator
from app.google_delete_events import GoogleEventDeleter
from app.google_events import GoogleEventReader
from app.google_update_events import GoogleEventUpdater

ADAPTER_FAILURES: dict[ProviderFailure, dict[str, Exception]] = {
    ProviderFailure.ACCESS_DENIED: {
        "create": EventCreationDeniedError(),
        "get": EventAccessDeniedError(),
        "replace": EventUpdateDeniedError(),
        "delete": EventDeletionDeniedError(),
    },
    ProviderFailure.UNEXPECTED_RESPONSE: {
        "create": EventCreationUnconfirmedError(),
        "get": CalendarProviderError(),
        "replace": EventUpdateProviderError(),
        "delete": EventDeletionUnconfirmedError(),
    },
    ProviderFailure.UNAVAILABLE: {
        "create": EventCreationProviderUnavailableError(),
        "get": EventReadUnavailableError(),
        "replace": EventUpdateProviderUnavailableError(),
        "delete": EventDeletionProviderUnavailableError(),
    },
    ProviderFailure.UNCERTAIN_WRITE: {
        "create": EventCreationUnconfirmedError(),
        "replace": EventUpdateUnconfirmedError(),
    },
}


class FailingAdapters:
    """Raise one Team 5 adapter error per operation, as the Google adapters do."""

    def __init__(self, failure: ProviderFailure) -> None:
        self.errors = ADAPTER_FAILURES[failure]

    def create_event(self, request: CreateEvent) -> NoReturn:
        raise self.errors["create"]

    def get_event(self, event_id: str) -> NoReturn:
        raise self.errors["get"]

    def update_event(self, event_id: str, request: ReplaceEvent) -> NoReturn:
        raise self.errors["replace"]

    def delete_event(self, event_id: str) -> NoReturn:
        raise self.errors["delete"]


def failing_google_service(failure: ProviderFailure) -> CalendarService:
    """Return `GoogleCalendarService` whose adapters all fail with `failure`."""
    adapters = FailingAdapters(failure)
    return GoogleCalendarService(
        creator=adapters, reader=adapters, updater=adapters, deleter=adapters
    )


class TestGoogleCalendarServiceConformance(CalendarServiceConformance):
    @pytest.fixture
    def service(
        self, google_service: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> CalendarService:
        monkeypatch.setattr("app.google_events.calendar_client", lambda: google_service)
        return GoogleCalendarService(
            creator=GoogleEventCreator(),
            reader=GoogleEventReader(),
            updater=GoogleEventUpdater(),
            deleter=GoogleEventDeleter(),
        )

    @pytest.fixture
    def failing_service(self) -> FailingServiceFactory:
        return failing_google_service


@pytest.mark.skipif(
    os.environ.get("CALENDAR_LIVE_CONFORMANCE") != "1",
    reason="set CALENDAR_LIVE_CONFORMANCE=1 to write to the real Google Calendar",
)
class TestLiveGoogleCalendarServiceConformance(CalendarServiceConformance):
    """Runs the suite against the real primary calendar; every event is deleted."""

    @pytest.fixture
    def service(self) -> CalendarService:
        return GoogleCalendarService(
            creator=GoogleEventCreator(),
            reader=GoogleEventReader(),
            updater=GoogleEventUpdater(),
            deleter=GoogleEventDeleter(),
        )

    @pytest.fixture
    def failing_service(self) -> FailingServiceFactory:
        return failing_google_service
