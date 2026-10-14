from typing import cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

from app.google_auth import CalendarAuthenticationError


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> Mock:
    service = Mock()
    monkeypatch.setattr("app.google_events.calendar_client", lambda: service)
    return cast(Mock, service.events.return_value.get.return_value.execute)


def timed_event() -> dict[str, object]:
    return {
        "id": "google-event",
        "summary": "Provider meeting",
        "start": {"dateTime": "2026-10-05T10:00:00-04:00"},
        "end": {"dateTime": "2026-10-05T11:00:00-04:00"},
        "htmlLink": "https://example.com/private-provider-field",
    }


def test_google_fields_are_translated(client: TestClient, provider: Mock) -> None:
    provider.return_value = timed_event()

    response = client.get("/events/google-event")

    assert response.status_code == 200
    assert response.json() == {
        "id": "google-event",
        "title": "Provider meeting",
        "start_time": "2026-10-05T10:00:00-04:00",
        "end_time": "2026-10-05T11:00:00-04:00",
    }


def test_untitled_event_returns_empty_title(client: TestClient, provider: Mock) -> None:
    data = timed_event()
    del data["summary"]
    provider.return_value = data

    response = client.get("/events/google-event")

    assert response.status_code == 200
    assert response.json()["title"] == ""


def test_all_day_event_is_rejected(client: TestClient, provider: Mock) -> None:
    provider.return_value = {
        "id": "all-day",
        "summary": "All day",
        "start": {"date": "2026-10-05"},
        "end": {"date": "2026-10-06"},
    }

    response = client.get("/events/all-day")

    assert response.status_code == 422
    assert response.json() == {"detail": "Only timed events are supported"}


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
def test_provider_failure_is_not_not_found(
    client: TestClient, provider: Mock, status: int
) -> None:
    provider.side_effect = HttpError(
        Mock(status=status, reason="Provider failure"),
        b'{"error": {"message": "Sensitive provider message"}}',
    )

    response = client.get("/events/google-event")

    assert response.status_code == 502
    assert response.json() == {"detail": "Calendar provider request failed"}


def test_network_failure_returns_bad_gateway(
    client: TestClient, provider: Mock
) -> None:
    provider.side_effect = TimeoutError("network timeout")

    response = client.get("/events/google-event")

    assert response.status_code == 502
    assert response.json() == {"detail": "Calendar provider request failed"}


@pytest.mark.parametrize(
    "data",
    [
        None,
        {"id": "broken"},
        {"id": "broken", "start": {}, "end": {}},
        {
            "id": "broken",
            "start": {"dateTime": "invalid"},
            "end": {"dateTime": "2026-10-05T11:00:00Z"},
        },
    ],
)
def test_malformed_provider_data_returns_bad_gateway(
    client: TestClient, provider: Mock, data: object
) -> None:
    provider.return_value = data

    response = client.get("/events/broken")

    assert response.status_code == 502
    assert response.json() == {"detail": "Calendar provider request failed"}


def test_authentication_required_returns_service_unavailable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.google_events.calendar_client",
        Mock(side_effect=CalendarAuthenticationError),
    )

    response = client.get("/events/google-event")

    assert response.status_code == 503
    assert response.json() == {"detail": "Calendar authentication required"}


@pytest.mark.parametrize(
    "outcome", ["success", "not-found", "http-error", "timeout", "malformed", "all-day"]
)
def test_google_client_is_closed_after_request(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    service = Mock()
    execute = service.events.return_value.get.return_value.execute
    execute.return_value = timed_event()
    expected_status = 200
    if outcome in {"not-found", "http-error"}:
        status = 404 if outcome == "not-found" else 500
        execute.side_effect = HttpError(
            Mock(status=status, reason="Failure"), b'{"error": {"message": "Failure"}}'
        )
        expected_status = 404 if status == 404 else 502
    elif outcome == "timeout":
        execute.side_effect = TimeoutError("timeout")
        expected_status = 502
    elif outcome == "malformed":
        execute.return_value = None
        expected_status = 502
    elif outcome == "all-day":
        execute.return_value = {
            "id": "all-day",
            "start": {"date": "2026-10-05"},
            "end": {"date": "2026-10-06"},
        }
        expected_status = 422
    monkeypatch.setattr("app.google_events.calendar_client", lambda: service)

    response = client.get("/events/google-event")

    assert response.status_code == expected_status
    service.close.assert_called_once_with()
