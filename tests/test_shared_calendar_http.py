import json
import logging
from collections.abc import Iterator

import pytest
from calendar_contract import (
    CalendarError,
    CalendarService,
    CreateEvent,
    ErrorCode,
    Event,
    ReplaceEvent,
)
from fastapi.testclient import TestClient

from app.calendar_service_dependencies import get_calendar_service
from app.main import app

PAYLOAD = {
    "title": "Request title",
    "start": "2030-01-07T15:00:00Z",
    "end": "2030-01-07T15:30:00Z",
}
ROUTES = [
    ("POST", "/events", "create_event", "create", 201),
    ("GET", "/events/test-event", "get_event", "get", 200),
    ("PUT", "/events/test-event", "replace_event", "replace", 200),
    ("PATCH", "/events/test-event", "update_event", "replace", 200),
    ("DELETE", "/events/test-event", "delete_event", "delete", 204),
]


class ControlledCalendarService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.error: CalendarError | None = None
        self.event = Event(id="test-event", **{**PAYLOAD, "title": "Stored title"})

    def record(self, operation: str, value: object) -> None:
        self.calls.append((operation, value))
        if self.error is not None:
            raise self.error

    def create(self, request: CreateEvent) -> Event:
        self.record("create", request)
        return self.event

    def get(self, event_id: str) -> Event:
        self.record("get", event_id)
        return self.event

    def replace(self, event_id: str, request: ReplaceEvent) -> Event:
        self.record("replace", (event_id, request))
        return self.event

    def delete(self, event_id: str) -> None:
        self.record("delete", event_id)


@pytest.fixture
def service() -> ControlledCalendarService:
    return ControlledCalendarService()


@pytest.fixture
def client(service: ControlledCalendarService) -> Iterator[TestClient]:
    def controlled_service() -> CalendarService:
        return service

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_calendar_service] = controlled_service
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.mark.parametrize(("method", "path", "operation", "called", "status"), ROUTES)
def test_routes_use_the_shared_service_dependency(
    client: TestClient,
    service: ControlledCalendarService,
    method: str,
    path: str,
    operation: str,
    called: str,
    status: int,
) -> None:
    response = client.request(
        method, path, json=PAYLOAD if method in ("POST", "PUT", "PATCH") else None
    )

    assert response.status_code == status
    assert len(service.calls) == 1
    assert service.calls[0][0] == called
    if method == "POST":
        assert service.calls[0][1] == CreateEvent(**PAYLOAD)
    elif method in ("PUT", "PATCH"):
        assert service.calls[0][1] == ("test-event", ReplaceEvent(**PAYLOAD))
    else:
        assert service.calls[0][1] == "test-event"
    if method == "DELETE":
        assert response.content == b""
    else:
        assert response.json() == service.event.model_dump()


@pytest.mark.parametrize(("method", "path", "operation", "called", "success"), ROUTES)
@pytest.mark.parametrize(
    ("code", "status", "retryable"),
    [
        (ErrorCode.INVALID_INPUT, 422, False),
        (ErrorCode.NOT_FOUND, 404, False),
        (ErrorCode.ACCESS_DENIED, 403, False),
        (ErrorCode.PROVIDER_ERROR, 502, False),
        (ErrorCode.PROVIDER_UNAVAILABLE, 503, True),
    ],
)
def test_shared_failures_have_one_sanitized_http_response_and_log(
    client: TestClient,
    service: ControlledCalendarService,
    caplog: pytest.LogCaptureFixture,
    method: str,
    path: str,
    operation: str,
    called: str,
    success: int,
    code: ErrorCode,
    status: int,
    retryable: bool,
) -> None:
    service.error = CalendarError(
        code,
        "Operation failed.",
        retryable,
        details={"provider": True, "raw": "private-provider-details"},
    )
    with caplog.at_level(logging.WARNING, logger="calendar_service"):
        response = client.request(
            method,
            path,
            json=PAYLOAD if method in ("POST", "PUT", "PATCH") else None,
            headers={"Authorization": "Bearer private-token"},
        )

    assert response.status_code == status
    assert response.json() == {
        "error": {
            "code": code.value,
            "message": "Operation failed.",
            "retryable": retryable,
        }
    }
    [record] = [
        r
        for r in caplog.records
        if r.name == "calendar_service" and r.levelno >= logging.WARNING
    ]
    assert (
        json.loads(record.getMessage()).items()
        >= {
            "operation": operation,
            "error": code.value,
            "provider": True,
            "status": status,
        }.items()
    )
    assert record.exc_info is None
    assert "private" not in response.text + caplog.text
