from copy import deepcopy
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/events"),
        ("PUT", "/events/test-event"),
        ("PATCH", "/events/test-event"),
    ],
)
@pytest.mark.parametrize(
    "change",
    [
        {"start_time": "2026-11-04T15:00:00Z"},
        {"end_time": "2026-11-04T16:00:00Z"},
        {"location": "Unsupported field"},
        {"start": "2026-11-04 15:00:00Z"},
        {"start": "2026-11-04T15:00:00+0000"},
    ],
)
def test_shared_inputs_reject_legacy_unknown_and_non_rfc3339_fields(
    client: TestClient,
    google_service: MagicMock,
    provider_events: dict[str, dict[str, object]],
    method: str,
    path: str,
    change: dict[str, object],
) -> None:
    payload = {
        "title": "Migration check",
        "start": "2026-11-04T15:00:00Z",
        "end": "2026-11-04T16:00:00Z",
        **change,
    }
    before = deepcopy(provider_events)

    response = client.request(method, path, json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"
    assert response.json()["error"]["retryable"] is False
    assert provider_events == before
    google_service.events.assert_not_called()


@pytest.mark.parametrize(
    ("method", "path", "status"),
    [
        ("POST", "/events", 201),
        ("PUT", "/events/test-event", 200),
        ("PATCH", "/events/test-event", 200),
    ],
)
def test_google_boundary_preserves_fractional_strings_and_trims_write_title(
    client: TestClient, google_service: MagicMock, method: str, path: str, status: int
) -> None:
    payload = {
        "title": "  Precision check  ",
        "start": "2026-11-04T10:00:00.123456789-05:00",
        "end": "2026-11-04T10:00:00.123456790-05:00",
    }

    response = client.request(method, path, json=payload)

    assert response.status_code == status
    event = response.json()
    assert set(event) == {"id", "title", "start", "end"}
    assert event["title"] == "Precision check"
    assert event["start"] == payload["start"]
    assert event["end"] == payload["end"]
    write = (
        google_service.events.return_value.insert
        if method == "POST"
        else google_service.events.return_value.patch
    )
    assert write.call_args.kwargs["body"] == {
        "summary": "Precision check",
        "start": {"dateTime": payload["start"]},
        "end": {"dateTime": payload["end"]},
    }
    write.return_value.execute.assert_called_once_with(num_retries=0)
    fetched = client.get(f"/events/{event['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == event
