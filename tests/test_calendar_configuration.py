"""Exercise configured Calendar selection through the normal HTTP dependencies."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

PAYLOAD = {
    "title": "Member 2 configuration check",
    "start": "2030-01-07T15:00:00Z",
    "end": "2030-01-07T15:30:00Z",
}


@pytest.mark.parametrize("implementation", [None, "google"])
def test_configured_google_creates_and_cleans_up(
    client: TestClient,
    google_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    implementation: str | None,
) -> None:
    if implementation is None:
        monkeypatch.delenv("CALENDAR_IMPLEMENTATION", raising=False)
    else:
        monkeypatch.setenv("CALENDAR_IMPLEMENTATION", implementation)
    response = client.post("/events", json=PAYLOAD)
    assert response.status_code == 201
    assert response.json() == {"id": "google-event-1", **PAYLOAD}
    google_service.events.return_value.insert.return_value.execute.assert_called_once_with(
        num_retries=0
    )
    assert client.delete("/events/google-event-1").status_code == 204
    assert client.get("/events/google-event-1").status_code == 404


@pytest.mark.parametrize("implementation", ["", "googlle", "private-invalid-value"])
def test_invalid_configuration_never_calls_google(
    client: TestClient,
    google_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    implementation: str,
) -> None:
    monkeypatch.setenv("CALENDAR_IMPLEMENTATION", implementation)
    response = client.post("/events", json=PAYLOAD)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_unavailable"
    assert response.json()["error"]["retryable"] is False
    assert "private-invalid-value" not in response.text
    google_service.events.assert_not_called()
