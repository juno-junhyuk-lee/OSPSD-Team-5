"""Normal route wiring must validate before constructing provider dependencies."""

from collections.abc import Iterator
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.workflow import WorkflowErrorResponse

PATH = "/workflows/scheduled-issues"
VALID = b'{"title":"test","start":"2030-01-07T15:00:00Z","end":"2030-01-07T15:30:00Z"}'


@pytest.fixture(autouse=True)
def configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "TRELLO_API_KEY",
        "TRELLO_TOKEN",
        "TRELLO_LIST_ID",
        "STORAGE_ROOT_PATH",
        "K_SERVICE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CALENDAR_MODE", "local")
    monkeypatch.setenv("CALENDAR_IMPLEMENTATION", "unsupported")
    assert not app.dependency_overrides


@pytest.fixture
def constructors() -> Iterator[list[Mock]]:
    with (
        patch(
            "app.issue_tracker_dependencies.TrelloIssueProvider",
            side_effect=AssertionError("Unexpected provider construction"),
        ) as issue,
        patch(
            "app.calendar_service_dependencies.GoogleCalendarService",
            side_effect=AssertionError("Unexpected provider construction"),
        ) as calendar,
    ):
        yield [issue, calendar]


@pytest.mark.parametrize("configured_issue", [False, True])
@pytest.mark.parametrize(
    "body,media,status",
    [
        (b"", "application/json", 400),
        (b"", None, 400),
        (b"  ", "application/json", 400),
        (b"{", "application/json", 400),
        (b"\xff", "application/json", 400),
        (b"null", "application/json", 422),
        (b'{"title":"SECRET","start":"2030-01-07T15:00:00Z"}', "application/json", 422),
        (
            b'{"title":"SECRET","start":"2030-01-07T15:00:00Z"}',
            "application/problem+json",
            422,
        ),
        (VALID.replace(b'"test"', b"7"), "application/json", 422),
        (VALID.replace(b'"test"', b'"   "'), "application/json", 422),
        (VALID.replace(b"15:30:00", b"14:30:00"), "application/json", 422),
        (VALID[:-1] + b',"extra":"SECRET"}', "application/json", 422),
        (VALID, "text/plain", 422),
        (VALID, None, 422),
    ],
)
def test_invalid_requests_win_over_provider_configuration(
    body: bytes,
    media: str | None,
    status: int,
    configured_issue: bool,
    monkeypatch: pytest.MonkeyPatch,
    constructors: list[Mock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    if configured_issue:
        monkeypatch.setenv("TRELLO_API_KEY", "synthetic")
        monkeypatch.setenv("TRELLO_TOKEN", "synthetic")
        monkeypatch.setenv("TRELLO_LIST_ID", "a" * 24)
    with TestClient(app) as client:
        headers = {"Content-Type": media} if media is not None else {}
        response = client.post(PATH, content=body, headers=headers)
    assert response.status_code == status
    error = WorkflowErrorResponse.model_validate(response.json()).error
    assert error.code.value == "invalid_input"
    assert error.step == "validate" and error.leftovers == []
    assert not error.retryable
    assert "SECRET" not in response.text + caplog.text
    for constructor in constructors:
        constructor.assert_not_called()


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
def test_valid_body_still_reports_missing_issue_configuration(
    constructors: list[Mock],
    encoding: str,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            PATH,
            content=VALID.decode().encode(encoding),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 503
    error = WorkflowErrorResponse.model_validate(response.json()).error
    assert error.step == "issue" and error.leftovers == []
    for constructor in constructors:
        constructor.assert_not_called()


def test_hosted_auth_still_precedes_body_validation(
    monkeypatch: pytest.MonkeyPatch,
    constructors: list[Mock],
) -> None:
    monkeypatch.setenv("CALENDAR_MODE", "hosted")
    with patch(
        "app.runtime.validate_hosted_config",
        return_value=b"synthetic-bearer-value-32-characters",
    ):
        with TestClient(app) as client:
            response = client.post(
                PATH, content=b"", headers={"Content-Type": "application/json"}
            )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert set(response.json()["error"]) == {"code", "message", "retryable"}
    for constructor in constructors:
        constructor.assert_not_called()
