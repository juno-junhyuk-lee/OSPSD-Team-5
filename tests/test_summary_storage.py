"""Controlled checks for summary storage through the normal workflow dependency."""

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.calendar_service_dependencies import get_calendar_service
from app.main import app
from app.storage_client import HttpDocumentStorage
from app.summary_storage import DocumentSummaryStore, SummaryStorageError
from app.workflow import WorkflowErrorResponse
from app.workflow_dependencies import get_workflow_issue_provider
from tests.test_workflow import PAYLOAD, FakeCalendar, FakeIssues


@pytest.fixture(autouse=True)
def storage_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in tuple(os.environ):
        if key.startswith("DROPBOX_") or key.startswith("STORAGE_"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("STORAGE_ROOT_PATH", "/team5")
    monkeypatch.setenv("DROPBOX_APP_KEY", "test-key")
    monkeypatch.setenv("DROPBOX_APP_SECRET", "test-secret")
    monkeypatch.setenv("DROPBOX_REFRESH_TOKEN", "test-refresh")


@pytest.mark.parametrize(
    "mode", ["success", "no_id", "conflict", "timeout", "mismatch", "read_failure"]
)
def test_workflow_uses_storage_and_preserves_failure_certainty(mode: str) -> None:
    uploaded: dict[str, bytes] = {}
    calls: list[str] = []

    def upload(local_path: str, path: str, *, overwrite: bool) -> SimpleNamespace:
        calls.append("create")
        assert overwrite is False
        if mode == "conflict":
            raise FileExistsError("SECRET")
        if mode == "timeout":
            raise ConnectionError("SECRET")
        uploaded["path"] = path.encode()
        uploaded["file"] = Path(local_path).read_bytes()
        return SimpleNamespace(
            id=None if mode == "no_id" else "stored-id",
            name=path.rsplit("/", 1)[1],
            path=path,
            size=len(uploaded["file"]),
            modified=None,
            etag=None,
        )

    def download(path: str, local_path: str) -> None:
        calls.append("download")
        assert path == uploaded["path"].decode()
        if mode == "read_failure":
            raise FileNotFoundError("SECRET")
        Path(local_path).write_bytes(
            b"wrong bytes" if mode == "mismatch" else uploaded["file"]
        )

    provider = Mock()
    provider.upload_file.side_effect = upload
    provider.download_file.side_effect = download

    issues, calendar = FakeIssues(), FakeCalendar()
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_workflow_issue_provider] = lambda: issues
    app.dependency_overrides[get_calendar_service] = lambda: calendar
    caller = TestClient(app)
    try:
        # Keep the real package wrapper and normal FastAPI storage dependency.
        # Only its lower-level provider client and SDK are controlled.
        with (
            patch("dropbox.Dropbox") as sdk,
            patch("dropbox_client_impl.DropboxClient", return_value=provider),
            patch(
                "app.storage_http.StorageHttpTransport.request",
                side_effect=AssertionError("Unexpected HTTP storage"),
            ),
        ):
            response = caller.post(
                "/workflows/scheduled-issues", json={**PAYLOAD, "title": "일정 확인"}
            )
            sdk.return_value.close.assert_called_once_with()
    finally:
        app.dependency_overrides = previous
        caller.close()
    assert "SECRET" not in response.text
    if mode in {"success", "no_id"}:
        assert response.status_code == 201
        summary = response.json()["summary"]
        assert summary["markdown"].encode() == uploaded["file"]
        assert "일정 확인" in uploaded["file"].decode()
        assert summary["id"] == (
            uploaded["path"].decode() if mode == "no_id" else "stored-id"
        )
        assert calls == ["create", "download"]
    else:
        assert response.status_code == 502
        error = WorkflowErrorResponse.model_validate(response.json()).error
        assert error.step == "summary" and not error.retryable
        assert calls.count("create") == 1
        if mode == "conflict":
            assert error.leftovers == []
            assert issues.calls[-1] == ("delete", "issue-1")
            assert calendar.calls[-1] == ("delete", "event-1")
            assert calls == ["create"]
        else:
            assert [item.kind for item in error.leftovers] == [
                "issue",
                "event",
                "summary",
            ]
            summary = response.json()["error"]["leftovers"][-1]
            assert summary == {
                "kind": "summary",
                "id": None,
                "state": "uncertain",
                "path": "/team5/scheduled-issue-issue-1-event-1.md",
            }
            assert all(
                "path" not in item
                for item in response.json()["error"]["leftovers"][:-1]
            )
            assert [call[0] for call in issues.calls] == ["create"]
            assert [call[0] for call in calendar.calls] == ["create"]


@pytest.mark.parametrize("root", [None, "/", "/team5/../other", "/team5/", "bad\nroot"])
def test_bad_root_fails_before_any_write(
    root: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    if root is None:
        monkeypatch.delenv("STORAGE_ROOT_PATH", raising=False)
    else:
        monkeypatch.setenv("STORAGE_ROOT_PATH", root)
    issues, calendar = FakeIssues(), FakeCalendar()
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_workflow_issue_provider] = lambda: issues
    app.dependency_overrides[get_calendar_service] = lambda: calendar
    try:
        with TestClient(app) as caller:
            response = caller.post("/workflows/scheduled-issues", json=PAYLOAD)
    finally:
        app.dependency_overrides = previous
    assert response.status_code == 503
    error = WorkflowErrorResponse.model_validate(response.json()).error
    assert error.step == "summary" and error.leftovers == []
    assert not error.retryable
    assert issues.calls == calendar.calls == []


@pytest.mark.parametrize(
    "failure", ["missing_key", "missing_token", "dotenv", "constructor"]
)
def test_package_configuration_failure_is_public_503_before_writes(
    failure: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    if failure == "missing_key":
        monkeypatch.delenv("DROPBOX_APP_KEY")
    elif failure == "missing_token":
        monkeypatch.delenv("DROPBOX_REFRESH_TOKEN")
    elif failure == "dotenv":
        monkeypatch.delenv("PYTHON_DOTENV_DISABLED")
    issues, calendar = FakeIssues(), FakeCalendar()
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_workflow_issue_provider] = lambda: issues
    app.dependency_overrides[get_calendar_service] = lambda: calendar
    try:
        with patch(
            "dropbox.Dropbox", side_effect=ValueError("SECRET credentials")
        ) as sdk:
            with TestClient(app) as caller:
                response = caller.post("/workflows/scheduled-issues", json=PAYLOAD)
            assert sdk.call_count == (1 if failure == "constructor" else 0)
    finally:
        app.dependency_overrides = previous
    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "provider_unavailable",
            "message": "The summary storage is not configured or unavailable.",
            "retryable": False,
            "step": "summary",
            "leftovers": [],
        }
    }
    assert issues.calls == calendar.calls == []


@pytest.mark.parametrize(
    "name", ["", ".", "..", "../escape.md", "a/b.md", "a\\b.md", "bad\nname"]
)
def test_bad_summary_filename_cannot_escape_root(name: str) -> None:
    def unexpected(request: httpx.Request) -> httpx.Response:
        raise AssertionError("unexpected HTTP")

    with httpx.Client(
        base_url="https://storage.example/", transport=httpx.MockTransport(unexpected)
    ) as client:
        store = DocumentSummaryStore(HttpDocumentStorage(client), "/team5")
        with pytest.raises(SummaryStorageError) as caught:
            store.save_summary(name, "text")
    assert not caught.value.may_have_applied
