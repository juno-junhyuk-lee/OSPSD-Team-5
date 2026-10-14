from types import SimpleNamespace

import pytest

from app.google_calendar import get_primary_calendar


def test_provider_metadata_is_translated(monkeypatch: pytest.MonkeyPatch) -> None:
    class Service:
        def __enter__(self) -> "Service":
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def calendars(self) -> "Service":
            return self

        def get(self, *, calendarId: str) -> SimpleNamespace:
            assert calendarId == "primary"
            return SimpleNamespace(
                execute=lambda: {
                    "id": "private-account-id",
                    "summary": "Real title",
                    "timeZone": "Europe/London",
                    "etag": "hidden",
                }
            )

    monkeypatch.setattr(
        "app.google_calendar.Credentials.from_authorized_user_file",
        lambda path: object(),
    )
    monkeypatch.setattr("app.google_calendar.build", lambda *args, **kwargs: Service())

    assert get_primary_calendar().model_dump() == {
        "id": "primary",
        "title": "Real title",
        "time_zone": "Europe/London",
    }
