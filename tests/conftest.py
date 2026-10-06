from collections.abc import Iterator
from copy import deepcopy
from itertools import count
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

from app import google_create_events, google_delete_events
from app.main import app


@pytest.fixture
def provider_events() -> dict[str, dict[str, object]]:
    return {
        "test-event": {
            "id": "test-event",
            "summary": "Example Event",
            "start": {"dateTime": "2026-10-05T18:00:00Z"},
            "end": {"dateTime": "2026-10-05T19:00:00Z"},
        }
    }


@pytest.fixture
def google_service(
    provider_events: dict[str, dict[str, object]],
) -> Iterator[MagicMock]:
    with (
        patch.object(google_create_events, "load_credentials"),
        patch.object(google_create_events, "build") as build,
        patch.object(google_delete_events, "load_credentials"),
        patch.object(google_delete_events, "build", build),
    ):
        sdk = build.return_value.__enter__.return_value
        insert = sdk.events.return_value.insert
        ids = count(1)

        def execute(*, num_retries: int = 0) -> dict[str, object]:
            body = insert.call_args.kwargs["body"]
            event = {
                "id": f"google-event-{next(ids)}",
                "summary": body["summary"],
                "start": body["start"],
                "end": body["end"],
                "htmlLink": "https://calendar.google.com/example",
            }
            provider_events[str(event["id"])] = deepcopy(event)
            return deepcopy(event)

        insert.return_value.execute.side_effect = execute
        delete = sdk.events.return_value.delete

        def delete_execute(*, num_retries: int = 0) -> str:
            event_id = delete.call_args.kwargs["eventId"]
            if event_id not in provider_events:
                raise HttpError(Mock(status=404, reason="Not Found"), b"")
            del provider_events[event_id]
            return ""

        delete.return_value.execute.side_effect = delete_execute
        yield sdk


@pytest.fixture
def client(
    google_service: MagicMock,
    provider_events: dict[str, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    def provider_get(*, calendarId: str, eventId: str) -> Mock:
        assert calendarId == "primary"

        def execute() -> dict[str, object]:
            if eventId not in provider_events:
                raise HttpError(
                    Mock(status=404, reason="Not Found"),
                    b'{"error": {"message": "Not found"}}',
                )
            return deepcopy(provider_events[eventId])

        return Mock(execute=execute)

    def retrieval_client() -> Mock:
        service = Mock()
        service.events.return_value.get.side_effect = provider_get
        return service

    monkeypatch.setattr("app.google_events.calendar_client", retrieval_client)
    with TestClient(app) as test_client:
        yield test_client
