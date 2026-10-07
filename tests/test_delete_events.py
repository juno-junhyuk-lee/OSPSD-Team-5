from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

from app import google_create_events, google_delete_events

EVENT = {
    "title": "Delete Me",
    "start_time": "2026-10-06T10:00:00-04:00",
    "end_time": "2026-10-06T11:00:00-04:00",
}


def test_delete_created_event(
    client: TestClient, provider_events: dict[str, dict[str, object]]
) -> None:
    event_id = client.post("/events", json=EVENT).json()["id"]

    response = client.delete(f"/events/{event_id}")

    assert response.status_code == 204
    assert response.content == b""
    # Google keeps cancelled events readable; our GET still returns them.
    assert provider_events[event_id]["status"] == "cancelled"
    assert client.get(f"/events/{event_id}").status_code == 200


def test_delete_leaves_other_events(client: TestClient) -> None:
    kept = client.post("/events", json=EVENT).json()
    deleted_id = client.post("/events", json=EVENT).json()["id"]

    assert client.delete(f"/events/{deleted_id}").status_code == 204

    assert client.get(f"/events/{kept['id']}").json() == kept
    assert client.get("/events/test-event").json()["title"] == "Example Event"


def test_delete_unknown_event_preserves_state(
    client: TestClient, provider_events: dict[str, dict[str, object]]
) -> None:
    before = dict(provider_events)

    response = client.delete("/events/missing-event")

    assert response.status_code == 404
    assert response.json() == {"detail": "Event not found"}
    assert provider_events == before


def test_repeated_delete_returns_not_found(client: TestClient) -> None:
    event_id = client.post("/events", json=EVENT).json()["id"]

    first = client.delete(f"/events/{event_id}")
    second = client.delete(f"/events/{event_id}")

    assert first.status_code == 204
    assert second.status_code == 404
    assert second.json() == {"detail": "Event not found"}


def test_delete_calls_google_without_retries(
    client: TestClient, google_service: MagicMock
) -> None:
    event_id = client.post("/events", json=EVENT).json()["id"]

    assert client.delete(f"/events/{event_id}").status_code == 204

    delete = google_service.events.return_value.delete
    delete.assert_called_once_with(
        calendarId="primary", eventId=event_id, sendUpdates="none"
    )
    delete.return_value.execute.assert_called_once_with(num_retries=0)


def test_gone_google_event_returns_not_found(
    client: TestClient, google_service: MagicMock
) -> None:
    execute = google_service.events.return_value.delete.return_value.execute
    execute.side_effect = HttpError(Mock(status=410, reason="Gone"), b"")

    response = client.delete("/events/test-event")

    assert response.status_code == 404
    assert response.json() == {"detail": "Event not found"}


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
    execute = google_service.events.return_value.delete.return_value.execute
    execute.side_effect = failure

    response = client.delete("/events/test-event")

    assert response.status_code == 502
    assert "secret" not in response.text
    assert "test-event" in provider_events


def test_missing_authorization_returns_unavailable(
    client: TestClient, google_service: MagicMock
) -> None:
    with patch.object(
        google_delete_events,
        "load_credentials",
        side_effect=google_create_events.GoogleCalendarSetupError("no token"),
    ):
        response = client.delete("/events/test-event")

    assert response.status_code == 503
    google_service.events.return_value.delete.assert_not_called()
