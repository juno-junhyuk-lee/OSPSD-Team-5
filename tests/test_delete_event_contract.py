import json
import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.event_deletion_dependencies import get_event_deleter
from app.event_deletion_provider import (
    EventDeleter,
    EventDeletionDeniedError,
    EventDeletionNotFoundError,
    EventDeletionUnavailableError,
    EventDeletionUnconfirmedError,
)
from app.google_delete_events import GoogleEventDeleter
from app.main import app


class ControlledEventDeleter:
    def __init__(self) -> None:
        self.event_ids = {"test-event", "other-event"}
        self.requested_ids: list[str] = []
        self.error: Exception | None = None

    def delete_event(self, event_id: str) -> None:
        self.requested_ids.append(event_id)
        if self.error is not None:
            raise self.error
        if event_id not in self.event_ids:
            raise EventDeletionNotFoundError
        self.event_ids.remove(event_id)


@pytest.fixture
def event_deleter() -> ControlledEventDeleter:
    return ControlledEventDeleter()


@pytest.fixture
def client(event_deleter: ControlledEventDeleter) -> Iterator[TestClient]:
    def controlled_deleter() -> EventDeleter:
        return event_deleter

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_event_deleter] = controlled_deleter
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def test_normal_requests_use_google() -> None:
    assert isinstance(get_event_deleter(), GoogleEventDeleter)


def test_delete_known_event(
    client: TestClient, event_deleter: ControlledEventDeleter
) -> None:
    response = client.delete("/events/test-event")

    assert response.status_code == 204
    assert response.content == b""
    assert event_deleter.requested_ids == ["test-event"]
    assert event_deleter.event_ids == {"other-event"}


def test_repeated_delete_returns_not_found(
    client: TestClient, event_deleter: ControlledEventDeleter
) -> None:
    first = client.delete("/events/test-event")
    second = client.delete("/events/test-event")

    assert first.status_code == 204
    assert second.status_code == 404
    assert second.json()["error"]["code"] == "not_found"
    assert event_deleter.requested_ids == ["test-event", "test-event"]


def test_delete_unknown_event(
    client: TestClient, event_deleter: ControlledEventDeleter
) -> None:
    response = client.delete("/events/missing-event")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Event not found.",
            "retryable": False,
        }
    }
    assert event_deleter.event_ids == {"test-event", "other-event"}


@pytest.mark.parametrize(
    ("error", "status", "code", "retryable"),
    [
        (EventDeletionDeniedError("private refusal"), 403, "access_denied", False),
        (
            EventDeletionUnavailableError("private authorization"),
            503,
            "provider_unavailable",
            False,
        ),
        (
            EventDeletionUnconfirmedError("private provider"),
            502,
            "provider_error",
            True,
        ),
    ],
)
def test_delete_failure_contract(
    client: TestClient,
    event_deleter: ControlledEventDeleter,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
    status: int,
    code: str,
    retryable: bool,
) -> None:
    event_deleter.error = error

    with caplog.at_level(logging.WARNING, logger="calendar_service"):
        response = client.delete("/events/test-event")

    body = response.json()
    assert response.status_code == status
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "retryable"}
    assert body["error"]["code"] == code
    assert body["error"]["retryable"] is retryable
    assert "private" not in response.text
    assert event_deleter.requested_ids == ["test-event"]
    [record] = caplog.records
    assert json.loads(record.getMessage()) == {
        "operation": "delete_event",
        "error": code,
        "provider": code != "provider_unavailable",
        "status": status,
    }
    assert "private" not in caplog.text


@pytest.mark.parametrize("event_id", ["bad%20id", "x" * 1025, "semi;colon", "dot.ted"])
def test_invalid_event_id_is_rejected_before_provider(
    client: TestClient, event_deleter: ControlledEventDeleter, event_id: str
) -> None:
    response = client.delete(f"/events/{event_id}")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"
    assert response.json()["error"]["retryable"] is False
    assert event_deleter.requested_ids == []


def test_recurring_instance_id_is_accepted(
    client: TestClient, event_deleter: ControlledEventDeleter
) -> None:
    event_deleter.event_ids.add("abc123_20261016T150000Z")

    response = client.delete("/events/abc123_20261016T150000Z")

    assert response.status_code == 204
