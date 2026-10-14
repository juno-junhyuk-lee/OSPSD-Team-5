from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.calendar_dependencies import get_calendar_reader
from app.calendar_provider import CalendarReader
from app.main import app
from app.models import Calendar


class ControlledCalendarReader:
    def __init__(self) -> None:
        self.calls = 0
        self.error: Exception | None = None

    def get_primary_calendar(self) -> Calendar:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return Calendar(
            id="primary", title="Team 5 Calendar", time_zone="America/New_York"
        )


@pytest.fixture
def calendar_reader() -> ControlledCalendarReader:
    return ControlledCalendarReader()


@pytest.fixture
def client(calendar_reader: ControlledCalendarReader) -> Iterator[TestClient]:
    def controlled_reader() -> CalendarReader:
        return calendar_reader

    # Use the public dependency boundary, without SDK mocks or credentials.
    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_calendar_reader] = controlled_reader
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def test_get_primary_calendar(
    client: TestClient, calendar_reader: ControlledCalendarReader
) -> None:
    response = client.get("/calendars/primary")

    assert response.status_code == 200
    assert response.json() == {
        "id": "primary",
        "title": "Team 5 Calendar",
        "time_zone": "America/New_York",
    }
    assert calendar_reader.calls == 1


def test_get_unknown_calendar(
    client: TestClient, calendar_reader: ControlledCalendarReader
) -> None:
    response = client.get("/calendars/missing-calendar")

    assert response.status_code == 404
    assert response.json() == {"detail": "Calendar not found"}
    assert calendar_reader.calls == 0


@pytest.mark.parametrize(
    ("error", "status", "detail"),
    [
        (OSError("missing token"), 503, "Google authorization unavailable"),
        (ValueError("invalid token"), 503, "Google authorization unavailable"),
        (RuntimeError("provider failed"), 502, "Calendar provider unavailable"),
    ],
)
def test_calendar_failure_contract(
    client: TestClient,
    calendar_reader: ControlledCalendarReader,
    error: Exception,
    status: int,
    detail: str,
) -> None:
    calendar_reader.error = error

    response = client.get("/calendars/primary")

    assert response.status_code == status
    assert response.json() == {"detail": detail}
    assert calendar_reader.calls == 1
