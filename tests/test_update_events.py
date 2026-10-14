from copy import deepcopy
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

from app import google_create_events, google_update_events

EVENT = {
    "title": "Original Meeting",
    "start_time": "2026-10-06T10:00:00-04:00",
    "end_time": "2026-10-06T11:00:00-04:00",
}

UPDATE = {
    "title": "  Updated Meeting  ",
    "start_time": "2026-10-06T11:00:00-04:00",
    "end_time": "2026-10-06T12:00:00-04:00",
}


def test_update_and_retrieve_event(client: TestClient) -> None:
    event_id = client.post("/events", json=EVENT).json()["id"]

    response = client.patch(f"/events/{event_id}", json=UPDATE)

    assert response.status_code == 200
    event = response.json()
    assert set(event) == {"id", "title", "start_time", "end_time"}
    assert event["id"] == event_id
    assert event["title"] == "Updated Meeting"
    assert datetime.fromisoformat(event["start_time"]) == datetime.fromisoformat(
        "2026-10-06T11:00:00-04:00"
    )
    assert datetime.fromisoformat(event["end_time"]) == datetime.fromisoformat(
        "2026-10-06T12:00:00-04:00"
    )
    assert client.get(f"/events/{event_id}").json() == event


def test_update_leaves_other_events(client: TestClient) -> None:
    kept = client.post("/events", json=EVENT).json()
    target_id = client.post("/events", json=EVENT).json()["id"]

    assert client.patch(f"/events/{target_id}", json=UPDATE).status_code == 200

    assert client.get(f"/events/{kept['id']}").json() == kept
    assert client.get("/events/test-event").json()["title"] == "Example Event"


def test_update_unknown_event_preserves_state(
    client: TestClient, provider_events: dict[str, dict[str, object]]
) -> None:
    before = deepcopy(provider_events)

    response = client.patch("/events/missing-event", json=UPDATE)

    assert response.status_code == 404
    assert response.json() == {"detail": "Event not found"}
    assert provider_events == before


@pytest.mark.parametrize("field", ["title", "start_time", "end_time"])
def test_missing_field_preserves_state(
    client: TestClient,
    provider_events: dict[str, dict[str, object]],
    field: str,
) -> None:
    event_id = client.post("/events", json=EVENT).json()["id"]
    before = deepcopy(provider_events)
    payload = dict(UPDATE)
    del payload[field]

    response = client.patch(f"/events/{event_id}", json=payload)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert provider_events == before


def test_equal_times_preserves_state(
    client: TestClient, provider_events: dict[str, dict[str, object]]
) -> None:
    event_id = client.post("/events", json=EVENT).json()["id"]
    before = deepcopy(provider_events)
    payload = {
        "title": "Bad Times",
        "start_time": "2026-10-06T11:00:00-04:00",
        "end_time": "2026-10-06T11:00:00-04:00",
    }

    response = client.patch(f"/events/{event_id}", json=payload)

    assert response.status_code == 422
    assert provider_events == before


def test_update_calls_google_without_retries(
    client: TestClient, google_service: MagicMock
) -> None:
    event_id = client.post("/events", json=EVENT).json()["id"]

    assert client.patch(f"/events/{event_id}", json=UPDATE).status_code == 200

    get_call = google_service.events.return_value.get
    get_call.assert_called_once_with(calendarId="primary", eventId=event_id)
    patch_call = google_service.events.return_value.patch
    patch_call.assert_called_once_with(
        calendarId="primary",
        eventId=event_id,
        body={
            "summary": "Updated Meeting",
            "start": {"dateTime": "2026-10-06T11:00:00-04:00"},
            "end": {"dateTime": "2026-10-06T12:00:00-04:00"},
        },
    )
    patch_call.return_value.execute.assert_called_once_with(num_retries=0)


def test_gone_google_event_returns_not_found(
    client: TestClient, google_service: MagicMock
) -> None:
    execute = google_service.events.return_value.patch.return_value.execute
    execute.side_effect = HttpError(Mock(status=410, reason="Gone"), b"")

    response = client.patch("/events/test-event", json=UPDATE)

    assert response.status_code == 404
    assert response.json() == {"detail": "Event not found"}


def test_patch_after_delete_does_not_call_patch(
    client: TestClient,
    google_service: MagicMock,
    provider_events: dict[str, dict[str, object]],
) -> None:
    event_id = client.post("/events", json=EVENT).json()["id"]
    assert client.delete(f"/events/{event_id}").status_code == 204
    assert provider_events[event_id]["status"] == "cancelled"

    response = client.patch(f"/events/{event_id}", json=UPDATE)

    assert response.status_code == 404
    assert response.json() == {"detail": "Event not found"}
    google_service.events.return_value.patch.assert_not_called()


@pytest.mark.parametrize(
    "failure",
    [
        HttpError(Mock(status=403, reason="Forbidden"), b'{"error": "secret detail"}'),
        HttpError(Mock(status=500, reason="Server Error"), b""),
        TimeoutError("network timeout"),
    ],
)
def test_provider_failure_returns_bad_gateway(
    client: TestClient,
    google_service: MagicMock,
    provider_events: dict[str, dict[str, object]],
    failure: Exception,
) -> None:
    execute = google_service.events.return_value.patch.return_value.execute
    execute.side_effect = failure

    response = client.patch("/events/test-event", json=UPDATE)

    assert response.status_code == 502
    assert "secret" not in response.text
    assert "test-event" in provider_events


def test_missing_authorization_returns_unavailable(
    client: TestClient, google_service: MagicMock
) -> None:
    with patch.object(
        google_update_events,
        "load_credentials",
        side_effect=google_create_events.GoogleCalendarSetupError("no token"),
    ):
        response = client.patch("/events/test-event", json=UPDATE)

    assert response.status_code == 503
    google_service.events.return_value.patch.assert_not_called()
