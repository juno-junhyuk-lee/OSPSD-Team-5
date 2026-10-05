from collections.abc import Iterator
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

from app.main import LOCAL_EVENTS, app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    original_events = LOCAL_EVENTS.copy()

    def local_google_response(calendarId: str, eventId: str) -> Mock:
        assert calendarId == "primary"
        if eventId not in LOCAL_EVENTS:
            response = Mock(status=404, reason="Not Found")
            raise HttpError(response, b'{"error": {"message": "Not found"}}')
        event = LOCAL_EVENTS[eventId]
        return Mock(
            execute=Mock(
                return_value={
                    "id": event.id,
                    "summary": event.title,
                    "start": {"dateTime": event.start_time.isoformat()},
                    "end": {"dateTime": event.end_time.isoformat()},
                }
            )
        )

    service = Mock()
    service.events.return_value.get.side_effect = local_google_response
    monkeypatch.setattr("app.google_events.calendar_client", lambda: service)
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        LOCAL_EVENTS.clear()
        LOCAL_EVENTS.update(original_events)
