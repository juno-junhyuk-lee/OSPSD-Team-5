from collections.abc import Iterator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.event_update_dependencies import get_event_updater
from app.event_update_provider import (
    EventUpdateNotFoundError,
    EventUpdater,
    EventUpdateUnavailableError,
    EventUpdateUnconfirmedError,
)
from app.main import app
from app.models import Event, UpdateEventRequest


class ControlledEventUpdater:
    def __init__(self) -> None:
        self.calls: list[tuple[str, UpdateEventRequest]] = []
        self.error: Exception | None = None

    def update_event(self, event_id: str, request: UpdateEventRequest) -> Event:
        self.calls.append((event_id, request))
        if self.error is not None:
            raise self.error
        return Event(
            id=event_id,
            title=request.title,
            start_time=request.start_time,
            end_time=request.end_time,
        )


@pytest.fixture
def updater() -> ControlledEventUpdater:
    return ControlledEventUpdater()


@pytest.fixture
def client(updater: ControlledEventUpdater) -> Iterator[TestClient]:
    def controlled_updater() -> EventUpdater:
        return updater

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_event_updater] = controlled_updater
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest.fixture
def payload() -> dict[str, object]:
    return {
        "title": "  Updated Meeting  ",
        "start_time": "2026-10-13T11:00:00-04:00",
        "end_time": "2026-10-13T12:00:00-04:00",
    }


def test_update_event_contract(
    client: TestClient, updater: ControlledEventUpdater, payload: dict[str, object]
) -> None:
    response = client.patch("/events/test-event", json=payload)

    assert response.status_code == 200
    assert response.json() == {
        "id": "test-event",
        "title": "Updated Meeting",
        "start_time": "2026-10-13T11:00:00-04:00",
        "end_time": "2026-10-13T12:00:00-04:00",
    }
    assert len(updater.calls) == 1
    event_id, request = updater.calls[0]
    assert event_id == "test-event"
    assert request.title == "Updated Meeting"
    assert request.start_time == datetime.fromisoformat("2026-10-13T11:00:00-04:00")
    assert request.end_time == datetime.fromisoformat("2026-10-13T12:00:00-04:00")


@pytest.mark.parametrize("field", ["title", "start_time", "end_time"])
def test_missing_field_does_not_call_updater(
    client: TestClient,
    updater: ControlledEventUpdater,
    payload: dict[str, object],
    field: str,
) -> None:
    del payload[field]

    response = client.patch("/events/test-event", json=payload)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert updater.calls == []


def test_equal_times_does_not_call_updater(
    client: TestClient, updater: ControlledEventUpdater, payload: dict[str, object]
) -> None:
    payload["end_time"] = payload["start_time"]

    response = client.patch("/events/test-event", json=payload)

    assert response.status_code == 422
    assert updater.calls == []


@pytest.mark.parametrize(
    ("error", "status", "detail"),
    [
        (
            EventUpdateNotFoundError("private missing"),
            404,
            "Event not found",
        ),
        (
            EventUpdateUnavailableError("private authorization"),
            503,
            "Google Calendar authorization is unavailable. "
            "Run scripts/google_calendar_auth.py.",
        ),
        (
            EventUpdateUnconfirmedError("private provider"),
            502,
            "Google Calendar update could not be confirmed. "
            "Check the calendar before retrying.",
        ),
    ],
)
def test_update_failure_contract(
    client: TestClient,
    updater: ControlledEventUpdater,
    payload: dict[str, object],
    error: Exception,
    status: int,
    detail: str,
) -> None:
    updater.error = error

    response = client.patch("/events/test-event", json=payload)

    assert response.status_code == status
    assert response.json() == {"detail": detail}
    assert len(updater.calls) == 1
