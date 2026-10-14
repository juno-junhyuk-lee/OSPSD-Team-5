from collections.abc import Iterator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.event_dependencies import get_event_reader
from app.event_provider import (
    CalendarAuthenticationError,
    CalendarProviderError,
    EventNotFoundError,
    EventReader,
    UnsupportedEventError,
)
from app.main import app
from app.models import Event


class ControlledEventReader:
    def __init__(self) -> None:
        self.requested_ids: list[str] = []
        self.error: Exception | None = None

    def get_event(self, event_id: str) -> Event:
        self.requested_ids.append(event_id)
        if self.error is not None:
            raise self.error
        if event_id != "test-event":
            raise EventNotFoundError
        return Event(
            id="test-event",
            title="Example Event",
            start_time=datetime.fromisoformat("2026-10-05T18:00:00Z"),
            end_time=datetime.fromisoformat("2026-10-05T19:00:00Z"),
        )


@pytest.fixture
def event_reader() -> ControlledEventReader:
    return ControlledEventReader()


@pytest.fixture
def client(event_reader: ControlledEventReader) -> Iterator[TestClient]:
    def controlled_reader() -> EventReader:
        return event_reader

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_event_reader] = controlled_reader
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def test_get_known_event(
    client: TestClient, event_reader: ControlledEventReader
) -> None:
    response = client.get("/events/test-event")

    assert response.status_code == 200
    assert response.json() == {
        "id": "test-event",
        "title": "Example Event",
        "start_time": "2026-10-05T18:00:00Z",
        "end_time": "2026-10-05T19:00:00Z",
    }
    assert event_reader.requested_ids == ["test-event"]


def test_get_unknown_event(
    client: TestClient, event_reader: ControlledEventReader
) -> None:
    response = client.get("/events/missing-event")

    assert response.status_code == 404
    assert response.json() == {"detail": "Event not found"}
    assert event_reader.requested_ids == ["missing-event"]


@pytest.mark.parametrize(
    ("error", "status", "detail"),
    [
        (
            UnsupportedEventError("private event"),
            422,
            "Only timed events are supported",
        ),
        (
            CalendarAuthenticationError("private authorization"),
            503,
            "Calendar authentication required",
        ),
        (
            CalendarProviderError("private provider"),
            502,
            "Calendar provider request failed",
        ),
    ],
)
def test_event_failure_contract(
    client: TestClient,
    event_reader: ControlledEventReader,
    error: Exception,
    status: int,
    detail: str,
) -> None:
    event_reader.error = error

    response = client.get("/events/test-event")

    assert response.status_code == status
    assert response.json() == {"detail": detail}
    assert event_reader.requested_ids == ["test-event"]
