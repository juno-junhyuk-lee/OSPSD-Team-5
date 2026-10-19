import json
import logging
from collections.abc import Iterator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.event_update_dependencies import get_event_updater
from app.event_update_provider import (
    EventUpdateDeniedError,
    EventUpdateNotFoundError,
    EventUpdater,
    EventUpdateUnavailableError,
    EventUpdateUnconfirmedError,
)
from app.google_update_events import GoogleEventUpdater
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


def test_normal_requests_use_google() -> None:
    assert isinstance(get_event_updater(), GoogleEventUpdater)


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


def test_success_does_not_log_failure(
    client: TestClient,
    payload: dict[str, object],
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="calendar_service"):
        assert client.patch("/events/test-event", json=payload).status_code == 200

    assert not [r for r in caplog.records if r.name == "calendar_service"]


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
    assert response.json()["error"]["code"] == "invalid_input"
    assert response.json()["error"]["retryable"] is False
    assert updater.calls == []


def test_equal_times_does_not_call_updater(
    client: TestClient, updater: ControlledEventUpdater, payload: dict[str, object]
) -> None:
    payload["end_time"] = payload["start_time"]

    response = client.patch("/events/test-event", json=payload)

    assert response.status_code == 422
    assert updater.calls == []


@pytest.mark.parametrize(
    ("error", "status", "code", "retryable", "provider"),
    [
        (EventUpdateNotFoundError("private missing"), 404, "not_found", False, True),
        (EventUpdateDeniedError("private refusal"), 403, "access_denied", False, True),
        (
            EventUpdateUnavailableError("private authorization"),
            503,
            "provider_unavailable",
            False,
            False,
        ),
        (
            EventUpdateUnavailableError("private remote auth", provider=True),
            503,
            "provider_unavailable",
            False,
            True,
        ),
        (
            EventUpdateUnconfirmedError("private provider"),
            502,
            "provider_error",
            False,
            True,
        ),
    ],
)
def test_update_failure_contract(
    client: TestClient,
    updater: ControlledEventUpdater,
    payload: dict[str, object],
    caplog: pytest.LogCaptureFixture,
    error: Exception,
    status: int,
    code: str,
    retryable: bool,
    provider: bool,
) -> None:
    updater.error = error

    with caplog.at_level(logging.WARNING, logger="calendar_service"):
        response = client.patch("/events/test-event", json=payload)

    body = response.json()
    assert response.status_code == status
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "retryable"}
    assert body["error"]["code"] == code
    assert body["error"]["retryable"] is retryable
    assert "private" not in response.text
    assert len(updater.calls) == 1
    [record] = [r for r in caplog.records if r.name == "calendar_service"]
    assert json.loads(record.getMessage()) == {
        "operation": "update_event",
        "error": code,
        "provider": provider,
        "status": status,
    }
    assert "private" not in caplog.text


@pytest.mark.parametrize("event_id", ["bad%20id", "x" * 1025, "semi;colon", "dot.ted"])
def test_invalid_event_id_is_rejected_before_provider(
    client: TestClient,
    updater: ControlledEventUpdater,
    event_id: str,
    payload: dict[str, object],
) -> None:
    response = client.patch(f"/events/{event_id}", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"
    assert response.json()["error"]["retryable"] is False
    assert updater.calls == []


def test_recurring_instance_id_is_accepted(
    client: TestClient, updater: ControlledEventUpdater, payload: dict[str, object]
) -> None:
    response = client.patch("/events/abc123_20261016T150000Z", json=payload)

    assert response.status_code == 200
    assert updater.calls[0][0] == "abc123_20261016T150000Z"
