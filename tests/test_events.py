import json
import logging
from collections.abc import Iterator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.event_dependencies import get_event_reader
from app.event_provider import (
    CalendarAuthenticationError,
    CalendarProviderError,
    EventAccessDeniedError,
    EventNotFoundError,
    EventReader,
    EventReadUnavailableError,
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
    client: TestClient,
    event_reader: ControlledEventReader,
    caplog: pytest.LogCaptureFixture,
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
    assert not [
        record for record in caplog.records if record.name == "calendar_service"
    ]


def test_get_unknown_event(
    client: TestClient, event_reader: ControlledEventReader
) -> None:
    response = client.get("/events/missing-event")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Event not found.",
            "retryable": False,
        }
    }
    assert event_reader.requested_ids == ["missing-event"]


@pytest.mark.parametrize(
    ("error", "status", "code", "message", "retryable", "provider"),
    [
        (
            UnsupportedEventError("private event"),
            422,
            "invalid_input",
            "Only timed events are supported.",
            False,
            True,
        ),
        (
            CalendarAuthenticationError("private authorization"),
            503,
            "provider_unavailable",
            "Calendar authentication required. Run scripts/google_calendar_auth.py.",
            False,
            False,
        ),
        (
            CalendarAuthenticationError("private remote authorization", provider=True),
            503,
            "provider_unavailable",
            "Calendar authentication required. Run scripts/google_calendar_auth.py.",
            False,
            True,
        ),
        (
            EventNotFoundError("private missing event"),
            404,
            "not_found",
            "Event not found.",
            False,
            True,
        ),
        (
            EventAccessDeniedError("private permission"),
            403,
            "access_denied",
            "Calendar denied access to this event.",
            False,
            True,
        ),
        (
            EventReadUnavailableError("private transport"),
            503,
            "provider_unavailable",
            "Calendar provider temporarily unavailable. Retry later.",
            True,
            True,
        ),
        (
            CalendarProviderError("private provider"),
            502,
            "provider_error",
            "Calendar provider request failed.",
            False,
            True,
        ),
    ],
)
def test_event_failure_contract(
    client: TestClient,
    event_reader: ControlledEventReader,
    error: Exception,
    status: int,
    code: str,
    message: str,
    retryable: bool,
    provider: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    event_reader.error = error

    response = client.get("/events/test-event")

    assert response.status_code == status
    assert response.json() == {
        "error": {"code": code, "message": message, "retryable": retryable}
    }
    assert event_reader.requested_ids == ["test-event"]
    [record] = [
        record for record in caplog.records if record.name == "calendar_service"
    ]
    assert json.loads(record.getMessage()) == {
        "operation": "get_event",
        "error": code,
        "provider": provider,
        "status": status,
    }
    assert record.levelno == (logging.ERROR if status >= 500 else logging.WARNING)
    assert record.exc_info is None
    assert "private" not in response.text
    assert "private" not in caplog.text


@pytest.mark.parametrize("event_id", ["bad%20id", "semi;colon", "dot.ted", "x" * 1025])
def test_invalid_id_is_rejected_before_reader(
    client: TestClient,
    event_reader: ControlledEventReader,
    event_id: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    response = client.get(f"/events/{event_id}")

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_input",
            "message": "Event ID must be 1-1024 letters, digits, '_' or '-'.",
            "retryable": False,
        }
    }
    assert event_reader.requested_ids == []
    [record] = [
        record for record in caplog.records if record.name == "calendar_service"
    ]
    assert json.loads(record.getMessage()) == {
        "operation": "get_event",
        "error": "invalid_input",
        "provider": False,
        "status": 422,
    }
    assert event_id not in caplog.text


@pytest.mark.parametrize(
    "event_id", ["a", "a" * 1024, "abc123_20261016T150000Z", "AbC_09-z"]
)
def test_valid_id_is_forwarded_to_reader(
    client: TestClient,
    event_reader: ControlledEventReader,
    event_id: str,
) -> None:
    response = client.get(f"/events/{event_id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert event_reader.requested_ids == [event_id]


def test_successful_recurring_instance_read(
    client: TestClient,
    event_reader: ControlledEventReader,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance_id = "abc123_20261016T150000Z"

    def get_instance(event_id: str) -> Event:
        return Event(
            id=event_id,
            title="Instance",
            start_time=datetime.fromisoformat("2026-10-16T15:00:00Z"),
            end_time=datetime.fromisoformat("2026-10-16T16:00:00Z"),
        )

    monkeypatch.setattr(event_reader, "get_event", get_instance)
    response = client.get(f"/events/{instance_id}")

    assert response.status_code == 200
    assert response.json()["id"] == instance_id
