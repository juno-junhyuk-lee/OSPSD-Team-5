import pytest
from fastapi.testclient import TestClient

from app.models import Calendar


@pytest.fixture(autouse=True)
def local_calendar(monkeypatch: pytest.MonkeyPatch) -> None:
    def get_calendar() -> Calendar:
        return Calendar(
            id="primary", title="Team 5 Calendar", time_zone="America/New_York"
        )

    monkeypatch.setattr("app.main.get_primary_calendar", get_calendar)


def test_get_primary_calendar(client: TestClient) -> None:
    response = client.get("/calendars/primary")

    assert response.status_code == 200
    assert response.json() == {
        "id": "primary",
        "title": "Team 5 Calendar",
        "time_zone": "America/New_York",
    }


def test_get_unknown_calendar(client: TestClient) -> None:
    response = client.get("/calendars/missing-calendar")

    assert response.status_code == 404
    assert response.json() == {"detail": "Calendar not found"}
