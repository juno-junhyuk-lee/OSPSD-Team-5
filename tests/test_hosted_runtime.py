import json
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
from fastapi.testclient import TestClient
from google.oauth2.credentials import Credentials

from app import google_auth, google_calendar, google_create_events
from app.main import app

DEMO_BEARER = "fake-demo-bearer-for-offline-test-000"


@pytest.fixture
def hosted_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    token = tmp_path / "oauth.json"
    token.write_text(
        json.dumps(
            {
                "client_id": "fake-client",
                "client_secret": "fake-secret",
                "refresh_token": "fake-refresh",
                "scopes": google_auth.HOSTED_SCOPES,
            }
        ),
        encoding="utf-8",
    )
    token.chmod(0o400)
    bearer = tmp_path / "bearer"
    bearer.write_text(DEMO_BEARER, encoding="utf-8")
    monkeypatch.setenv("K_SERVICE", "team5-test")
    monkeypatch.setenv("CALENDAR_RELEASE", "a" * 40)
    monkeypatch.setenv("CALENDAR_TOKEN_FILE", str(token))
    monkeypatch.setenv("CALENDAR_BEARER_FILE", str(bearer))
    return token


def test_hosted_health_and_authentication(hosted_files: Path) -> None:
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 204
        unauthorized = client.post("/events", json={})
        assert unauthorized.status_code == 401
        assert unauthorized.headers["WWW-Authenticate"] == "Bearer"
        assert client.get("/calendars/primary").status_code == 401
        assert (
            client.post(
                "/events",
                json={},
                headers={"Authorization": f"Bearer {DEMO_BEARER}"},
            ).status_code
            == 422
        )


def test_startup_error_excludes_bad_secret_contents(hosted_files: Path) -> None:
    hosted_files.chmod(0o600)
    hosted_files.write_text("secret-that-must-not-appear", encoding="utf-8")
    with (
        pytest.raises(RuntimeError, match="CALENDAR_TOKEN_FILE") as failure,
        TestClient(app),
    ):
        pytest.fail("Invalid authorization must prevent startup")
    assert "secret-that-must-not-appear" not in str(failure.value)
    assert failure.value.__suppress_context__


def test_hosted_adapters_reuse_refreshed_credentials_without_writing(
    hosted_files: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = hosted_files.read_bytes()

    def refresh(_request: object) -> None:
        credentials.valid = True

    credentials = Mock(valid=False)
    credentials.has_scopes.return_value = True
    credentials.refresh.side_effect = refresh
    monkeypatch.setattr(
        Credentials,
        "from_authorized_user_info",
        Mock(return_value=credentials),
    )
    build = MagicMock()
    monkeypatch.setattr(google_calendar, "build", build)
    result = build.return_value.__enter__.return_value
    result.calendars.return_value.get.return_value.execute.return_value = {
        "summary": "Example calendar",
        "timeZone": "UTC",
    }

    with TestClient(app):
        credentials.refresh.assert_not_called()
        assert google_auth.load_credentials() is credentials
        assert google_create_events.load_credentials() is credentials
        assert google_calendar.GoogleCalendarReader().get_primary_calendar().id == (
            "primary"
        )
        assert build.call_args.kwargs["credentials"] is credentials

    credentials.refresh.assert_called_once()
    assert hosted_files.read_bytes() == initial
