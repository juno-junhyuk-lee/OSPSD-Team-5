from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.event_deletion_dependencies import get_event_deleter
from app.event_deletion_provider import (
    EventDeleter,
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
    assert second.json() == {"detail": "Event not found"}
    assert event_deleter.requested_ids == ["test-event", "test-event"]


def test_delete_unknown_event(
    client: TestClient, event_deleter: ControlledEventDeleter
) -> None:
    response = client.delete("/events/missing-event")

    assert response.status_code == 404
    assert response.json() == {"detail": "Event not found"}
    assert event_deleter.event_ids == {"test-event", "other-event"}


@pytest.mark.parametrize(
    ("error", "status", "detail"),
    [
        (
            EventDeletionUnavailableError("private authorization"),
            503,
            "Google Calendar authorization is unavailable. "
            "Run scripts/google_calendar_auth.py.",
        ),
        (
            EventDeletionUnconfirmedError("private provider"),
            502,
            "Google Calendar deletion could not be confirmed. "
            "Retrying is safe; it returns 404 if the event is already gone.",
        ),
    ],
)
def test_delete_failure_contract(
    client: TestClient,
    event_deleter: ControlledEventDeleter,
    error: Exception,
    status: int,
    detail: str,
) -> None:
    event_deleter.error = error

    response = client.delete("/events/test-event")

    assert response.status_code == status
    assert response.json() == {"detail": detail}
    assert "private" not in response.text
    assert event_deleter.requested_ids == ["test-event"]
