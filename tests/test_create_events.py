from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.main import LOCAL_EVENTS


@pytest.fixture
def event_payload() -> dict[str, object]:
    return {
        "title": "Team Meeting",
        "start_time": "2026-10-05T10:00:00-04:00",
        "end_time": "2026-10-05T11:00:00-04:00",
    }


def test_create_and_retrieve_event(
    client: TestClient, event_payload: dict[str, object]
) -> None:
    event_payload["title"] = "  Team Meeting  "
    response = client.post("/events", json=event_payload)

    assert response.status_code == 201
    event = response.json()
    assert set(event) == {"id", "title", "start_time", "end_time"}
    assert isinstance(event["id"], str)
    assert event["id"]
    assert event["id"] != "test-event"
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
    client: TestClient, event_payload: dict[str, object], field: str
) -> None:
    del event_payload[field]
    before = LOCAL_EVENTS.copy()

    response = client.post("/events", json=event_payload)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert LOCAL_EVENTS == before


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
) -> None:
    event_payload[field] = value
    before = LOCAL_EVENTS.copy()

    response = client.post("/events", json=event_payload)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert LOCAL_EVENTS == before


def test_time_order_compares_instants(
    client: TestClient, event_payload: dict[str, object]
) -> None:
    event_payload["end_time"] = "2026-10-05T09:00:00-06:00"

    response = client.post("/events", json=event_payload)

    assert response.status_code == 201
