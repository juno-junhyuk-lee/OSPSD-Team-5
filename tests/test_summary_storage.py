"""Controlled checks for summary storage through the normal workflow dependency."""

from email import policy
from email.parser import BytesParser
from unittest.mock import patch

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
    monkeypatch.setenv("STORAGE_BASE_URL", "https://storage.example/")
    monkeypatch.setenv("STORAGE_ROOT_PATH", "/team5")
    monkeypatch.delenv("STORAGE_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("STORAGE_TIMEOUT_SECONDS", raising=False)


@pytest.mark.parametrize(
    "mode", ["success", "no_id", "conflict", "timeout", "mismatch", "read_failure"]
)
def test_workflow_uses_storage_and_preserves_failure_certainty(mode: str) -> None:
    uploaded: dict[str, bytes] = {}
    calls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        if request.method == "POST":
            if mode == "conflict":
                return httpx.Response(
                    409, json={"error": {"code": "conflict", "message": "SECRET"}}
                )
            if mode == "timeout":
                raise httpx.ReadTimeout("SECRET", request=request)
            message = BytesParser(policy=policy.default).parsebytes(
                b"Content-Type: "
                + request.headers["content-type"].encode()
                + b"\r\n\r\n"
                + request.content
            )
            for part in message.iter_parts():
                key = part.get_param("name", header="content-disposition")
                value = part.get_payload(decode=True)
                assert isinstance(key, str) and isinstance(value, bytes)
                uploaded[key] = value
            path = uploaded["path"].decode()
            return httpx.Response(
                201,
                json={
                    "id": None if mode == "no_id" else "stored-id",
                    "name": path.rsplit("/", 1)[1],
                    "path": path,
                    "size": len(uploaded["file"]),
                    "modified_at": None,
                    "etag": None,
                },
            )
        assert request.url.path == "/files/download"
        assert request.url.params["path"] == uploaded["path"].decode()
        if mode == "read_failure":
            return httpx.Response(404, json={"error": {"code": "not_found"}})
        return httpx.Response(
            200, content=b"wrong bytes" if mode == "mismatch" else uploaded["file"]
        )

    issues, calendar = FakeIssues(), FakeCalendar()
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_workflow_issue_provider] = lambda: issues
    app.dependency_overrides[get_calendar_service] = lambda: calendar
    remote = httpx.Client(
        base_url="https://storage.example/", transport=httpx.MockTransport(respond)
    )
    caller = TestClient(app)
    try:
        with patch("app.storage_settings.httpx.Client", return_value=remote):
            response = caller.post(
                "/workflows/scheduled-issues", json={**PAYLOAD, "title": "일정 확인"}
            )
    finally:
        app.dependency_overrides = previous
        caller.close()
    assert remote.is_closed
    assert "SECRET" not in response.text
    if mode in {"success", "no_id"}:
        assert response.status_code == 201
        summary = response.json()["summary"]
        assert summary["markdown"].encode() == uploaded["file"]
        assert "일정 확인" in uploaded["file"].decode()
        assert summary["id"] == (
            uploaded["path"].decode() if mode == "no_id" else "stored-id"
        )
        assert calls == ["POST", "GET"]
    else:
        assert response.status_code == 502
        error = WorkflowErrorResponse.model_validate(response.json()).error
        assert error.step == "summary" and not error.retryable
        assert calls.count("POST") == 1
        if mode == "conflict":
            assert error.leftovers == []
            assert issues.calls[-1] == ("delete", "issue-1")
            assert calendar.calls[-1] == ("delete", "event-1")
            assert calls == ["POST"]
        else:
            assert [item.kind for item in error.leftovers] == [
                "issue",
                "event",
                "summary",
            ]
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
