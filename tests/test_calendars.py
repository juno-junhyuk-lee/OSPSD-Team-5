import pytest
from fastapi.testclient import TestClient

from app.models import Calendar


@pytest.fixture(autouse=True)
def local_calendar(monkeypatch: pytest.MonkeyPatch) -> None:
    def get_calendar() -> Calendar:
        return Calendar(
            id="primary", title="Team 5 Calendar", time_zone="America/New_York"
        )

    monkeypatch.setattr("app.main.calendar_reader.get_primary_calendar", get_calendar)


def test_get_primary_calendar(client: TestClient) -> None:
    response = client.get("/calendars/primary")

    assert response.status_code == 200
    assert response.json() == {
        "id": "primary",
        "title": "Team 5 Calendar",
        "time_zone": "America/New_York",
    }


def test_get_unknown_calendar(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_lookup() -> Calendar:
        raise AssertionError("Unsupported IDs must not reach the provider")

    monkeypatch.setattr(
        "app.main.calendar_reader.get_primary_calendar", unexpected_lookup
    )
    response = client.get("/calendars/missing-calendar")

    assert response.status_code == 404
    assert response.json() == {"detail": "Calendar not found"}


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
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    status: int,
    detail: str,
) -> None:
    def failed_lookup() -> Calendar:
        raise error

    monkeypatch.setattr("app.main.calendar_reader.get_primary_calendar", failed_lookup)

    response = client.get("/calendars/primary")

    assert response.status_code == status
    assert response.json() == {"detail": detail}
