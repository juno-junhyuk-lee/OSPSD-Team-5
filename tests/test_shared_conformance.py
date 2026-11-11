"""Run the shared calendar-contract conformance suite against Team 5's service."""

import os
from collections.abc import Iterator
from typing import NoReturn
from unittest.mock import MagicMock

import pytest
from calendar_contract import CalendarService, CreateEvent, ReplaceEvent
from calendar_contract.conformance import (
    CalendarServiceConformance,
    FailingServiceFactory,
    ProviderFailure,
)
from fastapi.testclient import TestClient

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
from scripts.verify_put_live import verification_client
from tests.conformance_support import (
    HttpCalendarService,
    HttpInputConformance,
    SafeConformanceCleanup,
    cleanup_events,
)

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


class TestGoogleCalendarServiceConformance(
    SafeConformanceCleanup, CalendarServiceConformance
):
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


class TestHttpCalendarServiceConformance(
    HttpInputConformance, TestGoogleCalendarServiceConformance
):
    @pytest.fixture
    def service(self, client: TestClient) -> Iterator[CalendarService]:
        service = HttpCalendarService(client)
        try:
            yield service
        finally:
            cleanup_events(service, service.created_ids)


@pytest.mark.skipif(
    os.environ.get("CALENDAR_LIVE_CONFORMANCE") != "1",
    reason="set CALENDAR_LIVE_CONFORMANCE=1 to write to the real Google Calendar",
)
class TestLiveGoogleCalendarServiceConformance(
    SafeConformanceCleanup, CalendarServiceConformance
):
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


@pytest.mark.skipif(
    os.environ.get("CALENDAR_DEPLOYED_CONFORMANCE") != "1",
    reason="set CALENDAR_DEPLOYED_CONFORMANCE=1 to write through the deployed API",
)
class TestDeployedCalendarServiceConformance(
    HttpInputConformance, SafeConformanceCleanup, CalendarServiceConformance
):
    @pytest.fixture
    def service(self) -> Iterator[CalendarService]:
        if not os.environ.get("CALENDAR_VERIFY_URL"):
            pytest.fail("Deployed conformance requires CALENDAR_VERIFY_URL.")
        with verification_client() as client:
            assert client.get("/health").status_code == 200
            assert client.get("/ready").status_code == 204
            service = HttpCalendarService(client)
            try:
                yield service
            finally:
                cleanup_events(service, service.created_ids)

    @pytest.fixture
    def failing_service(self) -> FailingServiceFactory:
        # Failure hooks remain local; no faults are injected into demo.
        return failing_google_service
