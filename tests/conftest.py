from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import LOCAL_EVENTS, app


@pytest.fixture
def client() -> Iterator[TestClient]:
    original_events = LOCAL_EVENTS.copy()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        LOCAL_EVENTS.clear()
        LOCAL_EVENTS.update(original_events)
