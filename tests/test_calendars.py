import json
import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.calendar_dependencies import get_calendar_reader
from app.calendar_provider import (
    CalendarMetadataAccessDeniedError,
    CalendarMetadataAuthenticationError,
    CalendarMetadataNotFoundError,
    CalendarMetadataProviderError,
    CalendarMetadataUnavailableError,
    CalendarReader,
)
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
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Calendar not found.",
            "retryable": False,
        }
    }
    assert calendar_reader.calls == 0


@pytest.mark.parametrize(
    ("error", "status", "code", "message", "retryable", "provider"),
    [
        (
            CalendarMetadataNotFoundError(),
            404,
            "not_found",
            "Calendar not found.",
            False,
            True,
        ),
        (
            CalendarMetadataAuthenticationError(),
            503,
            "provider_unavailable",
            "Calendar authentication required. Run scripts/google_calendar_auth.py.",
            False,
            False,
        ),
        (
            CalendarMetadataAuthenticationError(provider=True),
            503,
            "provider_unavailable",
            "Calendar authentication required. Run scripts/google_calendar_auth.py.",
            False,
            True,
        ),
        (
            CalendarMetadataAccessDeniedError("secret"),
            403,
            "access_denied",
            "Calendar access denied.",
            False,
            True,
        ),
        (
            CalendarMetadataUnavailableError("secret"),
            503,
            "provider_unavailable",
            "Calendar provider temporarily unavailable.",
            True,
            True,
        ),
        (
            CalendarMetadataProviderError("secret"),
            502,
            "provider_error",
            "Calendar provider request failed.",
            False,
            True,
        ),
    ],
)
def test_calendar_failure_contract(
    client: TestClient,
    calendar_reader: ControlledCalendarReader,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
    status: int,
    code: str,
    message: str,
    retryable: bool,
    provider: bool,
) -> None:
    calendar_reader.error = error
    with caplog.at_level(logging.WARNING, logger="calendar_service"):
        response = client.get("/calendars/primary")

    assert response.status_code == status
    assert response.json() == {
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
        }
    }
    assert calendar_reader.calls == 1
    records = [r for r in caplog.records if r.name == "calendar_service"]
    assert len(records) == 1
    assert json.loads(records[0].getMessage()) == {
        "operation": "get_calendar",
        "error": code,
        "provider": provider,
        "status": status,
    }
    assert records[0].levelno == (logging.ERROR if status >= 500 else logging.WARNING)
    assert records[0].exc_info is None
    assert "secret" not in response.text + caplog.text


def test_unknown_calendar_log(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="calendar_service"):
        client.get("/calendars/private-id")
    records = [r for r in caplog.records if r.name == "calendar_service"]
    assert len(records) == 1
    assert json.loads(records[0].getMessage()) == {
        "operation": "get_calendar",
        "error": "not_found",
        "provider": False,
        "status": 404,
    }
    assert "private-id" not in records[0].getMessage()


def test_success_does_not_log_failure(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="calendar_service"):
        assert client.get("/calendars/primary").status_code == 200
    assert not [r for r in caplog.records if r.name == "calendar_service"]
