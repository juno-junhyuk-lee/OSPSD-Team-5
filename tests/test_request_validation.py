import json
import logging
from collections.abc import Iterator
from typing import cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.event_creation_dependencies import get_event_creator
from app.event_creation_provider import EventCreator
from app.event_update_dependencies import get_event_updater
from app.event_update_provider import EventUpdater
from app.main import app


@pytest.fixture
def validation_client() -> Iterator[tuple[TestClient, Mock, Mock]]:
    creator = Mock(spec=EventCreator)
    updater = Mock(spec=EventUpdater)

    def get_creator() -> EventCreator:
        return cast(EventCreator, creator)

    def get_updater() -> EventUpdater:
        return cast(EventUpdater, updater)

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_event_creator] = get_creator
    app.dependency_overrides[get_event_updater] = get_updater
    try:
        with TestClient(app) as client:
            yield client, creator, updater
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.mark.parametrize(
    ("method", "path", "operation"),
    [
        ("POST", "/events", "create_event"),
        ("PUT", "/events/private-event-id", "replace_event"),
        ("PATCH", "/events/private-event-id", "update_event"),
    ],
)
@pytest.mark.parametrize(
    ("body", "status"),
    [
        ("", 400),
        ("   ", 400),
        ('{"title": "private-title",', 400),
        ('{"title": "private-title"}', 422),
        ('{"title":"private-title", "start":"private-invalid-time", "end":null}', 422),
        ("null", 422),
        ("[]", 422),
        ('"private-string"', 422),
    ],
)
def test_validation_uses_shared_errors_without_leaking_inputs(
    validation_client: tuple[TestClient, Mock, Mock],
    caplog: pytest.LogCaptureFixture,
    method: str,
    path: str,
    operation: str,
    body: str,
    status: int,
) -> None:
    client, creator, updater = validation_client

    with caplog.at_level(logging.WARNING, logger="calendar_service"):
        response = client.request(
            method,
            path,
            content=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer private-token",
            },
        )

    assert response.status_code == status
    assert response.json() == {
        "error": {
            "code": "invalid_input",
            "message": "Invalid request. Check required fields, types, and values.",
            "retryable": False,
        }
    }
    creator.create_event.assert_not_called()
    updater.update_event.assert_not_called()
    [record] = [
        r
        for r in caplog.records
        if r.name == "calendar_service" and r.levelno >= logging.WARNING
    ]
    assert (
        json.loads(record.getMessage()).items()
        >= {
            "operation": operation,
            "error": "invalid_input",
            "provider": False,
            "status": status,
        }.items()
    )
    assert record.levelno == logging.WARNING
    assert record.exc_info is None
    assert "private" not in response.text + record.getMessage()


def test_openapi_documents_the_shared_validation_response(
    validation_client: tuple[TestClient, Mock, Mock],
) -> None:
    client, _, _ = validation_client
    schema = client.get("/openapi.json").json()

    for path, method in [
        ("/events", "post"),
        ("/events/{event_id}", "put"),
        ("/events/{event_id}", "patch"),
    ]:
        for status in ("400", "422"):
            response = schema["paths"][path][method]["responses"][status]
            assert response["content"]["application/json"]["schema"] == {
                "$ref": "#/components/schemas/ErrorResponse"
            }
