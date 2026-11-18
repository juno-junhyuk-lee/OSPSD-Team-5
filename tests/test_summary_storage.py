"""Controlled checks for summary storage through the normal workflow dependency."""

import os
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from cloud_storage_api import DocumentStorage
from dropbox.exceptions import ApiError  # type: ignore[import-untyped]
from fastapi.testclient import TestClient

from app.calendar_service_dependencies import get_calendar_service
from app.main import app
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
            raise FileExistsError("SECRET") from ApiError("test", None, None, None)
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
    "failure", ["missing_key", "missing_token", "dotenv", "constructor", "selector"]
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
    elif failure == "selector":
        monkeypatch.setenv("STORAGE_IMPLEMENTATION", "unknown")
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
    storage = Mock(spec=DocumentStorage)
    store = DocumentSummaryStore(storage, "/team5")
    with pytest.raises(SummaryStorageError) as caught:
        store.save_summary(name, "text")
    storage.create.assert_not_called()
    storage.download.assert_not_called()
    assert not caught.value.may_have_applied


def test_team1_selection_uses_the_real_package_for_workflow_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dropbox.files import FileMetadata  # type: ignore[import-untyped]

    monkeypatch.setenv("STORAGE_IMPLEMENTATION", "team1_dropbox")
    destination = "/team5/scheduled-issue-issue-1-event-1.md"
    metadata = FileMetadata(
        name=destination.rsplit("/", 1)[1],
        id="team1-file-id",
        client_modified=datetime(2026, 11, 17),
        server_modified=datetime(2026, 11, 17),
        rev="123456789",
        size=1,
        path_display=destination,
    )
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_workflow_issue_provider] = FakeIssues
    app.dependency_overrides[get_calendar_service] = FakeCalendar
    try:
        with (
            patch("dropbox.Dropbox") as sdk_type,
            patch(
                "dropbox_client_impl.DropboxDocumentStorage",
                side_effect=AssertionError("Wrong provider"),
            ) as team3,
        ):
            sdk = sdk_type.return_value
            sdk.files_upload.return_value = metadata
            sdk.files_download.side_effect = lambda path: (
                metadata,
                SimpleNamespace(content=sdk.files_upload.call_args.args[0]),
            )
            with TestClient(app) as caller:
                response = caller.post("/workflows/scheduled-issues", json=PAYLOAD)
            assert response.status_code == 201
            assert response.json()["summary"]["id"] == "team1-file-id"
            assert sdk.files_upload.call_args.args == (
                response.json()["summary"]["markdown"].encode("utf-8"),
                destination,
            )
            sdk.files_download.assert_called_once_with(destination)
            sdk.close.assert_called_once_with()
            team3.assert_not_called()
    finally:
        app.dependency_overrides = previous


@pytest.mark.parametrize(
    "selection,scenario,cleanup",
    [
        (selection, scenario, cleanup)
        for selection in ("team3_dropbox", "team1_dropbox")
        for scenario, cleanup in (
            ("connect_timeout", "clean"),
            ("connection_refused", "clean"),
            ("connect_timeout", "event_failed"),
            ("connect_timeout", "event_gone_issue_failed"),
            ("read_timeout", "clean"),
            ("unknown_connection", "clean"),
            ("applied_lost_reply", "clean"),
            ("read_connect_timeout", "clean"),
            ("read_untyped_error", "clean"),
            ("read_not_found", "clean"),
            ("read_mismatch", "clean"),
            ("unknown_shared_error", "clean"),
            ("bad_metadata", "clean"),
            ("untyped_error", "clean"),
            ("invalid_input", "clean"),
            ("conflict", "clean"),
            ("permission", "clean"),
        )
    ]
    + [("team3_dropbox", "upload_cleanup_permission", "clean")],
)
def test_sdk_failure_phase_controls_workflow_cleanup(
    scenario: str,
    cleanup: str,
    selection: str,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Failures pass through the selected package's REAL exception translation.
    monkeypatch.setenv("STORAGE_IMPLEMENTATION", selection)
    from calendar_contract import CalendarError, ErrorCode
    from cloud_storage_api import StorageError
    from dropbox import files, stone_validators  # type: ignore[import-untyped]
    from issue_tracker_contract import ErrorCode as IssueErrorCode
    from issue_tracker_contract import ServiceError as IssueServiceError
    from requests.exceptions import (
        ConnectionError as RequestsConnectionError,
    )
    from requests.exceptions import (
        ConnectTimeout,
        ReadTimeout,
    )
    from urllib3.exceptions import MaxRetryError, NewConnectionError

    uploaded: list[bytes] = []
    order: list[str] = []
    destination = "/team5/scheduled-issue-issue-1-event-1.md"
    metadata = files.FileMetadata(
        name="scheduled-issue-issue-1-event-1.md",
        id="stored-id",
        client_modified=datetime(2026, 11, 16),
        server_modified=datetime(2026, 11, 16),
        rev="123456789",
        size=1,
        path_display=destination,
    )

    def upload(content: bytes, path: str, **kwargs: object) -> object:
        order.append("create")
        assert path == destination
        if scenario == "connect_timeout":
            raise ConnectTimeout("SECRET")
        if scenario == "connection_refused":
            raise RequestsConnectionError(
                MaxRetryError(Mock(), "/", NewConnectionError(Mock(), "SECRET"))
            )
        if scenario == "read_timeout":
            raise ReadTimeout("SECRET")
        if scenario == "unknown_connection":
            # Even a suggestive message must not establish certainty.
            raise RequestsConnectionError("connection refused SECRET")
        if scenario == "invalid_input":
            raise stone_validators.ValidationError("SECRET")
        if scenario in {"conflict", "permission"}:
            reason = (
                files.WriteError.conflict(files.WriteConflictError.file)
                if scenario == "conflict"
                else files.WriteError.no_write_permission
            )
            raise ApiError(
                "test",
                files.UploadError.path(files.UploadWriteFailed(reason=reason)),
                None,
                None,
            )
        if scenario == "unknown_shared_error":
            raise StorageError("SECRET")
        uploaded.append(content)
        if scenario == "applied_lost_reply":
            raise ReadTimeout("SECRET")
        if scenario == "untyped_error":
            raise RuntimeError("SECRET")
        return object() if scenario == "bad_metadata" else metadata

    def download(*, download_path: str, path: str) -> object:
        order.append("download")
        assert path == destination
        if scenario == "read_mismatch":
            Path(download_path).write_bytes(b"wrong")
            return metadata
        if scenario == "read_not_found":
            raise ApiError(
                "test",
                files.DownloadError.path(files.LookupError.not_found),
                None,
                None,
            )
        if scenario == "read_untyped_error":
            raise RuntimeError("SECRET")
        raise ConnectTimeout("SECRET")

    def team1_download(path: str) -> object:
        if scenario == "read_mismatch":
            order.append("download")
            assert path == destination
            return metadata, SimpleNamespace(content=b"wrong")
        return download(download_path="unused", path=path)

    class UploadDirectory(TemporaryDirectory):
        def cleanup(self) -> None:
            super().cleanup()
            if scenario == "upload_cleanup_permission" and uploaded:
                raise PermissionError("SECRET")

    issues, calendar = FakeIssues(), FakeCalendar()
    delete_issue, delete_event = issues.delete_issue, calendar.delete

    def undo_issue(identifier: str) -> None:
        order.append("delete_issue")
        delete_issue(identifier)
        if cleanup == "event_gone_issue_failed":
            raise IssueServiceError(IssueErrorCode.PROVIDER_ERROR, "SECRET")

    def undo_event(identifier: str) -> None:
        order.append("delete_event")
        delete_event(identifier)
        if cleanup == "event_failed":
            raise CalendarError(ErrorCode.PROVIDER_ERROR, "SECRET", retryable=False)
        if cleanup == "event_gone_issue_failed":
            raise CalendarError(ErrorCode.NOT_FOUND, "SECRET", retryable=False)

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_workflow_issue_provider] = lambda: issues
    app.dependency_overrides[get_calendar_service] = lambda: calendar
    try:
        with (
            patch("dropbox.Dropbox") as sdk_type,
            patch(
                "dropbox_client_impl.document_storage.tempfile",
                SimpleNamespace(TemporaryDirectory=UploadDirectory),
            ),
            patch.object(issues, "delete_issue", side_effect=undo_issue),
            patch.object(calendar, "delete", side_effect=undo_event),
            caplog.at_level("INFO", logger="calendar_service"),
        ):
            sdk = sdk_type.return_value
            sdk.files_upload.side_effect = upload
            sdk.files_download_to_file.side_effect = download
            sdk.files_download.side_effect = team1_download
            with TestClient(app) as caller:
                response = caller.post("/workflows/scheduled-issues", json=PAYLOAD)
            sdk.close.assert_called_once_with()
            sdk.files_upload.assert_called_once()
            sdk.files_delete_v2.assert_not_called()
            sdk.files_get_metadata.assert_not_called()
    finally:
        app.dependency_overrides = previous
    assert response.status_code == 502
    error = response.json()["error"]
    assert not error["retryable"] and error["step"] == "summary"
    definite = scenario in {
        "connect_timeout",
        "connection_refused",
        "conflict",
        "permission",
    } or (scenario == "invalid_input" and selection == "team3_dropbox")
    if definite:
        assert uploaded == []
        assert order == ["create", "delete_event", "delete_issue"]
        expected = (
            []
            if cleanup == "clean"
            else [
                {
                    "kind": "event" if cleanup == "event_failed" else "issue",
                    "id": "event-1" if cleanup == "event_failed" else "issue-1",
                    "state": "created",
                }
            ]
        )
        assert error["leftovers"] == expected
    else:
        assert order == (
            ["create", "download"]
            if scenario
            in {
                "read_connect_timeout",
                "read_untyped_error",
                "read_not_found",
                "read_mismatch",
            }
            else ["create"]
        )
        assert [item["kind"] for item in error["leftovers"]] == [
            "issue",
            "event",
            "summary",
        ]
        assert error["leftovers"][-1] == {
            "kind": "summary",
            "id": None,
            "state": "uncertain",
            "path": destination,
        }
        if scenario in {
            "applied_lost_reply",
            "read_connect_timeout",
            "read_untyped_error",
            "read_not_found",
            "read_mismatch",
            "bad_metadata",
            "untyped_error",
            "upload_cleanup_permission",
        }:
            assert len(uploaded) == 1
    assert "SECRET" not in response.text + caplog.text
    assert destination not in caplog.text
