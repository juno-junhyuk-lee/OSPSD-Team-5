from collections.abc import Iterator
from itertools import count
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app import google_calendar
from app.main import LOCAL_EVENTS, app


@pytest.fixture
def google_service() -> Iterator[MagicMock]:
    with (
        patch.object(google_calendar, "load_credentials"),
        patch.object(google_calendar, "build") as build,
    ):
        sdk = build.return_value.__enter__.return_value
        insert = sdk.events.return_value.insert
        ids = count(1)

        def execute(*, num_retries: int = 0) -> dict[str, object]:
            body = insert.call_args.kwargs["body"]
            return {
                "id": f"google-event-{next(ids)}",
                "summary": body["summary"],
                "start": body["start"],
                "end": body["end"],
                "htmlLink": "https://calendar.google.com/example",
            }

        insert.return_value.execute.side_effect = execute
        yield sdk


@pytest.fixture
def client(google_service: MagicMock) -> Iterator[TestClient]:
    original_events = LOCAL_EVENTS.copy()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        LOCAL_EVENTS.clear()
        LOCAL_EVENTS.update(original_events)
