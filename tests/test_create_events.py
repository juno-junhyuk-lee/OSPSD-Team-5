from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Event as ThreadEvent
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from httplib2 import Response  # type: ignore[import-untyped]

from app import google_calendar
from app.main import LOCAL_EVENTS


@pytest.fixture
def event_payload() -> dict[str, object]:
    return {
        "title": "Team Meeting",
        "start_time": "2026-10-05T10:00:00-04:00",
        "end_time": "2026-10-05T11:00:00-04:00",
    }


def test_create_and_retrieve_event(
    client: TestClient, event_payload: dict[str, object], google_service: MagicMock
) -> None:
    event_payload["title"] = "  Team Meeting  "
    response = client.post("/events", json=event_payload)

    assert response.status_code == 201
    event = response.json()
    assert set(event) == {"id", "title", "start_time", "end_time"}
    assert isinstance(event["id"], str)
    assert event["id"]
    assert event["id"] != "test-event"
    assert event["id"] == "google-event-1"
    assert event["title"] == "Team Meeting"
    assert datetime.fromisoformat(event["start_time"]) == datetime.fromisoformat(
        "2026-10-05T10:00:00-04:00"
    )
    assert datetime.fromisoformat(event["end_time"]) == datetime.fromisoformat(
        "2026-10-05T11:00:00-04:00"
    )
    retrieved = client.get(f"/events/{event['id']}")
    assert retrieved.status_code == 200
    assert retrieved.json() == event
    assert client.get("/events/test-event").json()["title"] == "Example Event"
    google_service.events.return_value.insert.assert_called_once_with(
        calendarId="primary",
        body={
            "summary": "Team Meeting",
            "start": {"dateTime": "2026-10-05T10:00:00-04:00"},
            "end": {"dateTime": "2026-10-05T11:00:00-04:00"},
        },
    )


def test_repeated_creation_has_distinct_ids(
    client: TestClient, event_payload: dict[str, object]
) -> None:
    first = client.post("/events", json=event_payload)
    second = client.post("/events", json=event_payload)

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    for response in (first, second):
        event = response.json()
        assert client.get(f"/events/{event['id']}").json() == event


@pytest.mark.parametrize("field", ["title", "start_time", "end_time"])
def test_missing_field_preserves_state(
    client: TestClient,
    event_payload: dict[str, object],
    field: str,
    google_service: MagicMock,
) -> None:
    del event_payload[field]
    before = LOCAL_EVENTS.copy()

    response = client.post("/events", json=event_payload)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert LOCAL_EVENTS == before
    google_service.events.return_value.insert.assert_not_called()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", ""),
        ("title", " \t\n "),
        ("title", None),
        ("title", 123),
        ("start_time", "not-a-date"),
        ("end_time", "not-a-date"),
        ("start_time", "2026-10-05T10:00:00"),
        ("end_time", "2026-10-05T11:00:00"),
        ("start_time", 1791208800),
        ("start_time", "1791208800"),
        ("end_time", None),
        ("end_time", "2026-10-05T10:00:00-04:00"),
        ("end_time", "2026-10-05T09:59:59-04:00"),
        ("end_time", "2026-10-05T15:00:00+02:00"),
    ],
)
def test_invalid_field_preserves_state(
    client: TestClient,
    event_payload: dict[str, object],
    field: str,
    value: object,
    google_service: MagicMock,
) -> None:
    event_payload[field] = value
    before = LOCAL_EVENTS.copy()

    response = client.post("/events", json=event_payload)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert LOCAL_EVENTS == before
    google_service.events.return_value.insert.assert_not_called()


def test_time_order_compares_instants(
    client: TestClient, event_payload: dict[str, object]
) -> None:
    event_payload["end_time"] = "2026-10-05T09:00:00-06:00"

    response = client.post("/events", json=event_payload)

    assert response.status_code == 201


def test_missing_authorization_returns_503_without_local_creation(
    client: TestClient,
    event_payload: dict[str, object],
    google_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = LOCAL_EVENTS.copy()

    def unavailable() -> None:
        raise google_calendar.GoogleCalendarSetupError("Private setup details")

    monkeypatch.setattr(google_calendar, "load_credentials", unavailable)
    response = client.post("/events", json=event_payload)

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "Google Calendar authorization is unavailable. "
            "Run scripts/google_calendar_auth.py."
        )
    }
    assert LOCAL_EVENTS == before
    google_service.events.return_value.insert.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        HttpError(Response({"status": "403"}), b'{"error": "private details"}'),
        TimeoutError("Private transport details"),
    ],
)
def test_provider_failure_returns_502_without_local_creation(
    client: TestClient,
    event_payload: dict[str, object],
    google_service: MagicMock,
    error: Exception,
) -> None:
    before = LOCAL_EVENTS.copy()
    execute = google_service.events.return_value.insert.return_value.execute
    execute.side_effect = error

    response = client.post("/events", json=event_payload)

    assert response.status_code == 502
    assert response.json() == {
        "detail": (
            "Google Calendar creation could not be confirmed. "
            "Check the calendar before retrying."
        )
    }
    assert LOCAL_EVENTS == before
    execute.assert_called_once_with(num_retries=0)


def test_unusable_google_result_is_not_mirrored(
    client: TestClient, event_payload: dict[str, object], google_service: MagicMock
) -> None:
    before = LOCAL_EVENTS.copy()
    execute = google_service.events.return_value.insert.return_value.execute
    execute.side_effect = None
    execute.return_value = {"id": "google-event-123", "summary": "Team Meeting"}

    response = client.post("/events", json=event_payload)

    assert response.status_code == 502
    assert LOCAL_EVENTS == before
    execute.assert_called_once_with(num_retries=0)


def test_accepted_write_with_lost_response_is_not_retried(
    client: TestClient, event_payload: dict[str, object], google_service: MagicMock
) -> None:
    before = LOCAL_EVENTS.copy()
    accepted: list[str] = []

    def lose_response(*, num_retries: int = 0) -> None:
        accepted.append("google-accepted-event")
        raise TimeoutError("Write accepted, response lost")

    execute = google_service.events.return_value.insert.return_value.execute
    execute.side_effect = lose_response

    response = client.post("/events", json=event_payload)

    assert response.status_code == 502
    assert "Check the calendar before retrying" in response.json()["detail"]
    assert accepted == ["google-accepted-event"]
    assert LOCAL_EVENTS == before
    execute.assert_called_once_with(num_retries=0)


def test_get_completes_while_google_creation_is_waiting(
    client: TestClient, event_payload: dict[str, object], google_service: MagicMock
) -> None:
    started = ThreadEvent()
    release = ThreadEvent()

    def wait_for_provider(*, num_retries: int = 0) -> dict[str, object]:
        started.set()
        if not release.wait(timeout=10):
            raise TimeoutError("Test did not release provider")
        return {
            "id": "google-delayed-event",
            "summary": "Team Meeting",
            "start": {"dateTime": "2026-10-05T14:00:00Z"},
            "end": {"dateTime": "2026-10-05T15:00:00Z"},
        }

    execute = google_service.events.return_value.insert.return_value.execute
    execute.side_effect = wait_for_provider
    with ThreadPoolExecutor(max_workers=2) as pool:
        creation = pool.submit(client.post, "/events", json=event_payload)
        try:
            assert started.wait(timeout=5)
            retrieval = pool.submit(client.get, "/events/test-event")
            response = retrieval.result(timeout=5)
            assert response.status_code == 200
            assert response.json()["title"] == "Example Event"
            assert not creation.done()
        finally:
            release.set()
        assert creation.result(timeout=5).status_code == 201
