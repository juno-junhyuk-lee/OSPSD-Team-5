import json
import logging
from collections.abc import Iterator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.event_creation_dependencies import get_event_creator
from app.event_creation_provider import (
    EventCreationDeniedError,
    EventCreationUnavailableError,
    EventCreationUnconfirmedError,
    EventCreator,
)
from app.main import app
from app.models import CreateEventRequest, Event


class ControlledEventCreator:
    def __init__(self) -> None:
        self.requests: list[CreateEventRequest] = []
        self.error: Exception | None = None

    def create_event(self, request: CreateEventRequest) -> Event:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return Event(
            id=f"controlled-event-{len(self.requests)}",
            title=request.title,
            start_time=request.start_time,
            end_time=request.end_time,
        )


@pytest.fixture
def creator() -> ControlledEventCreator:
    return ControlledEventCreator()


@pytest.fixture
def client(creator: ControlledEventCreator) -> Iterator[TestClient]:
    def controlled_creator() -> EventCreator:
        return creator

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_event_creator] = controlled_creator
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest.fixture
def payload() -> dict[str, object]:
    return {
        "title": "  Team Meeting  ",
        "start_time": "2026-10-13T10:00:00-04:00",
        "end_time": "2026-10-13T11:00:00-04:00",
    }


def test_create_event_contract(
    client: TestClient,
    creator: ControlledEventCreator,
    payload: dict[str, object],
    caplog: pytest.LogCaptureFixture,
) -> None:
    response = client.post("/events", json=payload)

    assert response.status_code == 201
    assert response.json() == {
        "id": "controlled-event-1",
        "title": "Team Meeting",
        "start_time": "2026-10-13T10:00:00-04:00",
        "end_time": "2026-10-13T11:00:00-04:00",
    }
    assert len(creator.requests) == 1
    request = creator.requests[0]
    assert request.title == "Team Meeting"
    assert request.start_time == datetime.fromisoformat("2026-10-13T10:00:00-04:00")
    assert request.end_time == datetime.fromisoformat("2026-10-13T11:00:00-04:00")
    assert not [
        record for record in caplog.records if record.name == "calendar_service"
    ]


def test_repeated_creation_uses_returned_ids(
    client: TestClient, creator: ControlledEventCreator, payload: dict[str, object]
) -> None:
    first = client.post("/events", json=payload)
    second = client.post("/events", json=payload)

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == "controlled-event-1"
    assert second.json()["id"] == "controlled-event-2"
    assert len(creator.requests) == 2


@pytest.mark.parametrize("field", ["title", "start_time", "end_time"])
def test_missing_field_does_not_call_creator(
    client: TestClient,
    creator: ControlledEventCreator,
    payload: dict[str, object],
    field: str,
) -> None:
    del payload[field]

    response = client.post("/events", json=payload)

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_input",
            "message": "Invalid request. Check required fields, types, and values.",
            "retryable": False,
        }
    }
    assert creator.requests == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", " \t\n "),
        ("title", 123),
        ("start_time", "not-a-date"),
        ("start_time", "2026-10-13T10:00:00"),
        ("end_time", None),
        ("end_time", "2026-10-13T10:00:00-04:00"),
        ("end_time", "2026-10-13T15:00:00+02:00"),
    ],
)
def test_invalid_input_does_not_call_creator(
    client: TestClient,
    creator: ControlledEventCreator,
    payload: dict[str, object],
    field: str,
    value: object,
) -> None:
    payload[field] = value

    response = client.post("/events", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"
    assert response.json()["error"]["retryable"] is False
    assert creator.requests == []


def test_time_order_compares_instants(
    client: TestClient, creator: ControlledEventCreator, payload: dict[str, object]
) -> None:
    payload["end_time"] = "2026-10-13T09:00:00-06:00"

    response = client.post("/events", json=payload)

    assert response.status_code == 201
    assert len(creator.requests) == 1
    assert creator.requests[0].end_time == datetime.fromisoformat(
        "2026-10-13T11:00:00-04:00"
    )
    assert datetime.fromisoformat(
        response.json()["end_time"]
    ) == datetime.fromisoformat("2026-10-13T11:00:00-04:00")


@pytest.mark.parametrize(
    ("error", "status", "code", "message", "provider"),
    [
        (
            EventCreationUnavailableError("private authorization"),
            503,
            "provider_unavailable",
            "Google Calendar authorization is unavailable. "
            "Run scripts/google_calendar_auth.py.",
            False,
        ),
        (
            EventCreationUnavailableError("private refresh", provider=True),
            503,
            "provider_unavailable",
            "Google Calendar authorization is unavailable. "
            "Run scripts/google_calendar_auth.py.",
            True,
        ),
        (
            EventCreationDeniedError("private refusal"),
            403,
            "access_denied",
            "Google Calendar denied permission to create this event.",
            True,
        ),
        (
            EventCreationUnconfirmedError("private provider"),
            502,
            "provider_error",
            "Google Calendar creation could not be confirmed. "
            "Check the calendar before retrying.",
            True,
        ),
    ],
)
def test_creation_failure_contract(
    client: TestClient,
    creator: ControlledEventCreator,
    payload: dict[str, object],
    error: Exception,
    status: int,
    code: str,
    message: str,
    provider: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    creator.error = error

    with caplog.at_level(logging.WARNING, logger="calendar_service"):
        response = client.post("/events", json=payload)

    assert response.status_code == status
    assert response.json() == {
        "error": {"code": code, "message": message, "retryable": False}
    }
    assert len(creator.requests) == 1
    [record] = [r for r in caplog.records if r.name == "calendar_service"]
    assert json.loads(record.getMessage()) == {
        "operation": "create_event",
        "error": code,
        "provider": provider,
        "status": status,
    }
    assert record.levelno == (logging.ERROR if status >= 500 else logging.WARNING)
    assert record.exc_info is None
    assert "private" not in response.text + caplog.text
