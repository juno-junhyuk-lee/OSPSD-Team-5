"""Keep unsupported replacements read-only and preserve timed instances."""

from copy import deepcopy
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

PAYLOAD = {
    "title": "Replacement",
    "start": "2030-01-07T16:00:00Z",
    "end": "2030-01-07T17:00:00Z",
}


@pytest.mark.parametrize("method", ["PUT", "PATCH"])
@pytest.mark.parametrize("shape", ["all-day", "series", "all-day-instance"])
def test_unsupported_replacement_does_not_write(
    client: TestClient,
    google_service: MagicMock,
    provider_events: dict[str, dict[str, object]],
    method: str,
    shape: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    event = provider_events["test-event"]
    if shape in {"all-day", "all-day-instance"}:
        event["start"] = {"date": "2030-01-07"}
        event["end"] = {"date": "2030-01-08"}
    if shape == "series":
        event["recurrence"] = ["RRULE:FREQ=DAILY;COUNT=3"]
    if shape == "all-day-instance":
        event["recurringEventId"] = "parent-series"
        event["originalStartTime"] = {"date": "2030-01-07"}
    before = deepcopy(provider_events)

    response = client.request(method, "/events/test-event", json=PAYLOAD)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_input"
    assert response.json()["error"]["retryable"] is False
    assert provider_events == before
    google_service.events.return_value.patch.assert_not_called()
    records = [r for r in caplog.records if r.name == "calendar_service"]
    assert len(records) == 1
    assert PAYLOAD["title"] not in caplog.text


@pytest.mark.parametrize("method", ["PUT", "PATCH"])
def test_timed_instance_replacement_preserves_series_metadata(
    client: TestClient,
    google_service: MagicMock,
    provider_events: dict[str, dict[str, object]],
    method: str,
) -> None:
    instance_id = "series_20300107T150000Z"
    original = {"dateTime": "2030-01-07T15:00:00Z"}
    provider_events[instance_id] = {
        "id": instance_id,
        "summary": "Instance",
        "start": original,
        "end": {"dateTime": "2030-01-07T15:30:00Z"},
        "recurringEventId": "parent-series",
        "originalStartTime": deepcopy(original),
        "description": "Keep this field",
    }
    parent: dict[str, object] = {
        "id": "parent-series",
        "summary": "Parent",
        "start": original,
        "end": {"dateTime": "2030-01-07T15:30:00Z"},
        "recurrence": ["RRULE:FREQ=DAILY;COUNT=3"],
    }
    provider_events["parent-series"] = deepcopy(parent)

    response = client.request(method, f"/events/{instance_id}", json=PAYLOAD)

    assert response.status_code == 200
    assert response.json() == {"id": instance_id, **PAYLOAD}
    stored = provider_events[instance_id]
    assert stored["recurringEventId"] == "parent-series"
    assert stored["originalStartTime"] == original
    assert stored["description"] == "Keep this field"
    assert provider_events["parent-series"] == parent
    patch = google_service.events.return_value.patch
    assert patch.call_args.kwargs["eventId"] == instance_id
    assert set(patch.call_args.kwargs["body"]) == {"summary", "start", "end"}
    patch.return_value.execute.assert_called_once_with(num_retries=0)


def test_all_day_get_retains_existing_error_policy(
    client: TestClient, provider_events: dict[str, dict[str, object]]
) -> None:
    provider_events["test-event"]["start"] = {"date": "2030-01-07"}
    provider_events["test-event"]["end"] = {"date": "2030-01-08"}
    before = deepcopy(provider_events)

    response = client.get("/events/test-event")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"
    assert provider_events == before


def test_timed_series_can_be_read_without_changing_recurrence(
    client: TestClient, provider_events: dict[str, dict[str, object]]
) -> None:
    provider_events["test-event"]["recurrence"] = ["RRULE:FREQ=DAILY;COUNT=3"]
    before = deepcopy(provider_events)

    response = client.get("/events/test-event")

    assert response.status_code == 200
    assert set(response.json()) == {"id", "title", "start", "end"}
    assert provider_events == before


@pytest.mark.parametrize("start", [None, {"timeZone": "UTC"}])
def test_malformed_provider_times_are_rejected_before_patch(
    client: TestClient,
    google_service: MagicMock,
    provider_events: dict[str, dict[str, object]],
    start: object,
) -> None:
    provider_events["test-event"]["start"] = start
    before = deepcopy(provider_events)

    response = client.put("/events/test-event", json=PAYLOAD)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "provider_error"
    assert response.json()["error"]["retryable"] is False
    assert provider_events == before
    google_service.events.return_value.patch.assert_not_called()


@pytest.mark.parametrize("method", ["GET", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize(
    "event_id", ["x", "single-event", "series_20300107T150000Z", "x" * 1024]
)
def test_supported_http_ids_are_forwarded_unchanged(
    client: TestClient,
    google_service: MagicMock,
    provider_events: dict[str, dict[str, object]],
    method: str,
    event_id: str,
) -> None:
    provider_events[event_id] = {
        **deepcopy(provider_events["test-event"]),
        "id": event_id,
    }

    response = client.request(
        method,
        f"/events/{event_id}",
        json=PAYLOAD if method in {"PUT", "PATCH"} else None,
    )

    assert response.status_code == (204 if method == "DELETE" else 200)
    if method != "DELETE":
        assert response.json()["id"] == event_id
    sdk_method = "delete" if method == "DELETE" else "get"
    sdk_call = getattr(google_service.events.return_value, sdk_method)
    if method != "GET":
        assert sdk_call.call_args.kwargs["eventId"] == event_id


@pytest.mark.parametrize("method", ["GET", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize("event_id", ["bad.id", "bad@id", "x" * 1025])
def test_unsupported_http_id_is_rejected_before_provider(
    client: TestClient,
    google_service: MagicMock,
    method: str,
    event_id: str,
) -> None:
    response = client.request(
        method,
        f"/events/{event_id}",
        json=PAYLOAD if method in {"PUT", "PATCH"} else None,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"
    google_service.events.assert_not_called()
