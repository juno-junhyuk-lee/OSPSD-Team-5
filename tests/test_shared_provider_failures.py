import json
from unittest.mock import MagicMock, Mock

import pytest
from fastapi.testclient import TestClient
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

from app import google_create_events, google_delete_events

PAYLOAD = {
    "title": "Failure check",
    "start": "2030-01-07T15:00:00Z",
    "end": "2030-01-07T15:30:00Z",
}


@pytest.mark.parametrize(
    "failure", [TimeoutError("private"), HttpError(Mock(status=503), b"private")]
)
def test_delete_setup_outage_is_unavailable_before_writing(
    client: TestClient,
    google_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
) -> None:
    monkeypatch.setattr(google_delete_events, "build", Mock(side_effect=failure))

    response = client.delete("/events/test-event")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_unavailable"
    assert response.json()["error"]["retryable"] is True
    assert "private" not in response.text
    google_service.events.return_value.delete.assert_not_called()


@pytest.mark.parametrize(
    ("method", "path"), [("POST", "/events"), ("PUT", "/events/test-event")]
)
@pytest.mark.parametrize("phase", ["before-write", "write"])
@pytest.mark.parametrize(
    "failure",
    [TimeoutError("private-timeout"), HttpError(Mock(status=503), b"private")],
)
def test_write_phase_controls_error_and_retry_advice(
    client: TestClient,
    google_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    phase: str,
    failure: Exception,
) -> None:
    write = (
        google_service.events.return_value.insert
        if method == "POST"
        else google_service.events.return_value.patch
    )
    if phase == "before-write":
        if method == "POST":
            monkeypatch.setattr(
                google_create_events, "build", Mock(side_effect=failure)
            )
        else:
            google_service.events.return_value.get.side_effect = None
            google_service.events.return_value.get.return_value.execute.side_effect = (
                failure
            )
    else:
        write.return_value.execute.side_effect = failure

    response = client.request(method, path, json=PAYLOAD)

    assert response.status_code == (503 if phase == "before-write" else 502)
    assert response.json()["error"]["code"] == (
        "provider_unavailable" if phase == "before-write" else "provider_error"
    )
    assert response.json()["error"]["retryable"] is (phase == "before-write")
    assert "private" not in response.text
    if phase == "before-write":
        write.assert_not_called()
    else:
        write.return_value.execute.assert_called_once_with(num_retries=0)


@pytest.mark.parametrize(
    "failure",
    [
        HttpError(Mock(status=429), b"private"),
        HttpError(
            Mock(status=403),
            json.dumps(
                {
                    "error": {
                        "message": "private",
                        "errors": [{"reason": "rateLimitExceeded"}],
                    }
                }
            ).encode(),
        ),
    ],
)
@pytest.mark.parametrize(
    ("method", "path", "sdk_method"),
    [
        ("POST", "/events", "insert"),
        ("PUT", "/events/test-event", "patch"),
        ("DELETE", "/events/test-event", "delete"),
    ],
)
def test_explicit_rate_limit_is_unavailable_without_automatic_retry(
    client: TestClient,
    google_service: MagicMock,
    failure: Exception,
    method: str,
    path: str,
    sdk_method: str,
) -> None:
    execute = getattr(
        google_service.events.return_value, sdk_method
    ).return_value.execute
    execute.side_effect = failure

    response = client.request(
        method, path, json=PAYLOAD if method != "DELETE" else None
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_unavailable"
    assert response.json()["error"]["retryable"] is True
    execute.assert_called_once_with(num_retries=0)


def test_delete_authentication_rejection_is_not_permission_denial(
    client: TestClient, google_service: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    execute = google_service.events.return_value.delete.return_value.execute
    execute.side_effect = HttpError(Mock(status=401), b"private-auth")

    response = client.delete("/events/test-event")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_unavailable"
    assert response.json()["error"]["retryable"] is False
    [record] = [r for r in caplog.records if r.name == "calendar_service"]
    assert json.loads(record.getMessage())["provider"] is True
    assert "private" not in response.text + caplog.text
    execute.assert_called_once_with(num_retries=0)


@pytest.mark.parametrize("phase", ["read", "write"])
def test_unexpected_update_response_is_a_shared_provider_error(
    client: TestClient, google_service: MagicMock, phase: str
) -> None:
    method = "get" if phase == "read" else "patch"
    if phase == "read":
        google_service.events.return_value.get.side_effect = None
    execute = getattr(google_service.events.return_value, method).return_value.execute
    execute.side_effect = None
    execute.return_value = None

    response = client.put("/events/test-event", json=PAYLOAD)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "provider_error"
    assert response.json()["error"]["retryable"] is False
    if phase == "read":
        google_service.events.return_value.patch.assert_not_called()


def test_replacement_cannot_return_a_different_event_id(
    client: TestClient, google_service: MagicMock
) -> None:
    execute = google_service.events.return_value.patch.return_value.execute
    execute.side_effect = None
    execute.return_value = {
        "id": "wrong-event",
        "summary": "Failure check",
        "start": {"dateTime": PAYLOAD["start"]},
        "end": {"dateTime": PAYLOAD["end"]},
    }

    response = client.put("/events/test-event", json=PAYLOAD)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "provider_error"
    assert response.json()["error"]["retryable"] is False
    execute.assert_called_once_with(num_retries=0)
