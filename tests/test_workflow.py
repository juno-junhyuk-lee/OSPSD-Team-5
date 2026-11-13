"""Offline checks for the scheduled-issue workflow and its HTTP endpoint."""

import json
import logging
from collections.abc import Iterator

import pytest
from calendar_contract import (
    CalendarError,
    CalendarService,
    CreateEvent,
    ErrorCode,
    Event,
    ReplaceEvent,
)
from fastapi.testclient import TestClient
from issue_tracker_contract import ErrorCode as IssueErrorCode
from issue_tracker_contract import Issue, IssueProvider, IssueUpdate
from issue_tracker_contract import ServiceError as IssueServiceError

from app.main import app
from app.summary_storage import StoredSummary, SummaryStorageError, SummaryStore
from app.workflow import (
    ScheduledIssueRequest,
    ScheduledIssueWorkflow,
    WorkflowError,
    escape_markdown,
    render_summary,
    summary_name,
)
from app.workflow_dependencies import (
    get_scheduled_issue_workflow,
    get_summary_store,
    get_workflow_issue_provider,
)

PATH = "/workflows/scheduled-issues"
PAYLOAD = {
    "title": "Fix login bug",
    "start": "2030-01-07T15:00:00Z",
    "end": "2030-01-07T15:30:00Z",
}


class FakeIssues:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.create_error: IssueServiceError | None = None
        self.delete_error: IssueServiceError | None = None

    def create_issue(self, title: str) -> Issue:
        self.calls.append(("create", title))
        if self.create_error is not None:
            raise self.create_error
        return Issue(id="issue-1", title=title)

    def get_issue(self, issue_id: str, *, fresh: bool = False) -> Issue:
        raise AssertionError("not used")

    def update_issue(self, issue_id: str, changes: IssueUpdate) -> Issue:
        raise AssertionError("not used")

    def delete_issue(self, issue_id: str) -> None:
        self.calls.append(("delete", issue_id))
        if self.delete_error is not None:
            raise self.delete_error


class FakeCalendar:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.create_error: CalendarError | None = None
        self.delete_error: CalendarError | None = None

    def create(self, request: CreateEvent) -> Event:
        self.calls.append(("create", request))
        if self.create_error is not None:
            raise self.create_error
        return Event(
            id="event-1", title=request.title, start=request.start, end=request.end
        )

    def get(self, event_id: str) -> Event:
        raise AssertionError("not used")

    def replace(self, event_id: str, request: ReplaceEvent) -> Event:
        raise AssertionError("not used")

    def delete(self, event_id: str) -> None:
        self.calls.append(("delete", event_id))
        if self.delete_error is not None:
            raise self.delete_error


class FakeStore:
    def __init__(self) -> None:
        self.saved: list[tuple[str, str]] = []
        self.error: SummaryStorageError | None = None

    def save_summary(self, name: str, markdown: str) -> StoredSummary:
        self.saved.append((name, markdown))
        if self.error is not None:
            raise self.error
        return StoredSummary(id="summary-1")


@pytest.fixture
def issues() -> FakeIssues:
    return FakeIssues()


@pytest.fixture
def calendar() -> FakeCalendar:
    return FakeCalendar()


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def workflow(
    issues: FakeIssues, calendar: FakeCalendar, store: FakeStore
) -> ScheduledIssueWorkflow:
    return ScheduledIssueWorkflow(issues=issues, calendar=calendar, summaries=store)


@pytest.fixture
def client(workflow: ScheduledIssueWorkflow) -> Iterator[TestClient]:
    def controlled() -> ScheduledIssueWorkflow:
        return workflow

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_scheduled_issue_workflow] = controlled
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides = previous


def run(workflow: ScheduledIssueWorkflow, **changes: str) -> WorkflowError:
    with pytest.raises(WorkflowError) as raised:
        workflow.run(ScheduledIssueRequest(**{**PAYLOAD, **changes}))
    return raised.value


def leftovers(error: WorkflowError) -> list[dict[str, object]]:
    return [leftover.model_dump() for leftover in error.leftovers]


# Success


def test_success_runs_steps_in_order_and_stores_markdown(
    workflow: ScheduledIssueWorkflow,
    issues: FakeIssues,
    calendar: FakeCalendar,
    store: FakeStore,
) -> None:
    result = workflow.run(ScheduledIssueRequest(**PAYLOAD))

    assert issues.calls == [("create", "Fix login bug")]
    assert [call[0] for call in calendar.calls] == ["create"]
    assert calendar.calls[0][1] == CreateEvent(**PAYLOAD)
    assert result.issue == Issue(id="issue-1", title="Fix login bug")
    assert result.event.id == "event-1"
    assert result.summary.id == "summary-1"
    assert store.saved == [
        ("scheduled-issue-issue-1-event-1.md", result.summary.markdown)
    ]
    assert result.summary.markdown == (
        "# Fix login bug\n"
        "\n"
        "| Field | Value |\n"
        "| --- | --- |\n"
        "| Issue ID | `issue-1` |\n"
        "| Issue title | Fix login bug |\n"
        "| Event ID | `event-1` |\n"
        "| Start | 2030\\-01\\-07T15:00:00Z |\n"
        "| End | 2030\\-01\\-07T15:30:00Z |\n"
    )


def test_http_success_returns_201_with_all_parts(client: TestClient) -> None:
    response = client.post(PATH, json=PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["issue"] == {"id": "issue-1", "title": "Fix login bug"}
    assert body["event"]["id"] == "event-1"
    assert body["summary"]["id"] == "summary-1"
    assert body["summary"]["markdown"].startswith("# Fix login bug\n")


# Markdown


def test_markdown_escapes_untrusted_text() -> None:
    issue = Issue(id="a|b`c", title="**bold** [link](http://x) <script>")
    event = Event(
        id="e1",
        title="# Heading\nsecond | line",
        start="2030-01-07T15:00:00Z",
        end="2030-01-07T15:30:00Z",
    )

    markdown = render_summary(issue, event)

    assert markdown.splitlines()[0] == "# \\# Heading second \\| line"
    assert "| Issue ID | `a\\|b'c` |" in markdown
    assert "\\*\\*bold\\*\\* \\[link\\]\\(http://x\\) \\<script\\>" in markdown
    assert "<script>" not in markdown


def test_escape_collapses_whitespace() -> None:
    assert escape_markdown("  a\r\n\tb  ") == "a b"


def test_summary_name_is_path_safe() -> None:
    issue = Issue(id="../etc/passwd", title="t")
    event = Event(
        id="e/1", title="t", start="2030-01-07T15:00:00Z", end="2030-01-07T15:30:00Z"
    )

    name = summary_name(issue, event)

    assert name == "scheduled-issue-___etc_passwd-e_1.md"


# Validation happens before any write


@pytest.mark.parametrize(
    "changes",
    [
        {"title": "   "},
        {"title": "x" * 257},
        {"start": "not a time"},
        {"end": "2030-01-07T14:00:00Z"},
    ],
)
def test_invalid_input_makes_no_writes(
    changes: dict[str, str],
    workflow: ScheduledIssueWorkflow,
    issues: FakeIssues,
    calendar: FakeCalendar,
    store: FakeStore,
) -> None:
    error = run(workflow, **changes)

    assert (error.code, error.status, error.step) == (
        ErrorCode.INVALID_INPUT,
        422,
        "validate",
    )
    assert issues.calls == calendar.calls == store.saved == []


@pytest.mark.parametrize(
    "body",
    [
        {**PAYLOAD, "extra": 1},
        {"title": "t", "start": PAYLOAD["start"]},
        {**PAYLOAD, "title": 5},
    ],
)
def test_http_rejects_bad_shapes_without_writes(
    body: dict[str, object], client: TestClient, issues: FakeIssues
) -> None:
    response = client.post(PATH, json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"
    assert issues.calls == []


# Step 1: issue


@pytest.mark.parametrize(
    ("issue_code", "code", "status"),
    [
        (IssueErrorCode.INVALID_INPUT, ErrorCode.INVALID_INPUT, 422),
        (IssueErrorCode.ACCESS_DENIED, ErrorCode.ACCESS_DENIED, 403),
        (IssueErrorCode.SERVICE_NOT_CONFIGURED, ErrorCode.PROVIDER_UNAVAILABLE, 503),
        (IssueErrorCode.NOT_FOUND, ErrorCode.PROVIDER_ERROR, 502),
    ],
)
def test_definite_issue_failure_stops_before_calendar(
    issue_code: IssueErrorCode,
    code: ErrorCode,
    status: int,
    workflow: ScheduledIssueWorkflow,
    issues: FakeIssues,
    calendar: FakeCalendar,
) -> None:
    issues.create_error = IssueServiceError(
        issue_code, "remote SECRET", may_have_applied=False
    )

    error = run(workflow)

    assert (error.code, error.status, error.step) == (code, status, "issue")
    assert "SECRET" not in error.message
    assert error.leftovers == []
    assert calendar.calls == []


@pytest.mark.parametrize(
    "issue_error",
    [
        IssueServiceError(IssueErrorCode.PROVIDER_ERROR, "x", may_have_applied=True),
        IssueServiceError(
            IssueErrorCode.REQUEST_IN_PROGRESS, "x", may_have_applied=False
        ),
    ],
)
def test_uncertain_issue_creation_is_reported_not_retried(
    issue_error: IssueServiceError,
    workflow: ScheduledIssueWorkflow,
    issues: FakeIssues,
    calendar: FakeCalendar,
) -> None:
    issues.create_error = issue_error

    error = run(workflow)

    assert (error.code, error.step, error.retryable) == (
        ErrorCode.PROVIDER_ERROR,
        "issue",
        False,
    )
    assert leftovers(error) == [{"kind": "issue", "id": None, "state": "uncertain"}]
    assert issues.calls == [("create", "Fix login bug")]
    assert calendar.calls == []


# Step 2: calendar


def test_definite_calendar_failure_deletes_issue(
    workflow: ScheduledIssueWorkflow, issues: FakeIssues, calendar: FakeCalendar
) -> None:
    calendar.create_error = CalendarError(
        ErrorCode.PROVIDER_UNAVAILABLE, "Run scripts/x", retryable=True
    )

    error = run(workflow)

    assert (error.code, error.status, error.step) == (
        ErrorCode.PROVIDER_UNAVAILABLE,
        503,
        "event",
    )
    assert error.retryable is True
    assert error.leftovers == []
    assert issues.calls[-1] == ("delete", "issue-1")


def test_calendar_failure_reports_issue_when_cleanup_fails(
    workflow: ScheduledIssueWorkflow, issues: FakeIssues, calendar: FakeCalendar
) -> None:
    calendar.create_error = CalendarError(
        ErrorCode.ACCESS_DENIED, "denied", retryable=False
    )
    issues.delete_error = IssueServiceError(IssueErrorCode.PROVIDER_ERROR, "x")

    error = run(workflow)

    assert (error.code, error.step, error.retryable) == (
        ErrorCode.ACCESS_DENIED,
        "event",
        False,
    )
    assert leftovers(error) == [{"kind": "issue", "id": "issue-1", "state": "created"}]


def test_retry_advice_is_withdrawn_when_cleanup_leaves_issue(
    workflow: ScheduledIssueWorkflow, issues: FakeIssues, calendar: FakeCalendar
) -> None:
    calendar.create_error = CalendarError(
        ErrorCode.PROVIDER_UNAVAILABLE, "later", retryable=True
    )
    issues.delete_error = IssueServiceError(IssueErrorCode.ACCESS_DENIED, "x")

    error = run(workflow)

    assert error.retryable is False
    assert leftovers(error) == [{"kind": "issue", "id": "issue-1", "state": "created"}]


def test_issue_already_gone_counts_as_cleaned_up(
    workflow: ScheduledIssueWorkflow, issues: FakeIssues, calendar: FakeCalendar
) -> None:
    calendar.create_error = CalendarError(
        ErrorCode.ACCESS_DENIED, "denied", retryable=False
    )
    issues.delete_error = IssueServiceError(IssueErrorCode.NOT_FOUND, "gone")

    assert run(workflow).leftovers == []


def test_uncertain_calendar_creation_keeps_issue(
    workflow: ScheduledIssueWorkflow, issues: FakeIssues, calendar: FakeCalendar
) -> None:
    calendar.create_error = CalendarError(
        ErrorCode.PROVIDER_ERROR, "unconfirmed", retryable=False
    )

    error = run(workflow)

    assert (error.code, error.status, error.step) == (
        ErrorCode.PROVIDER_ERROR,
        502,
        "event",
    )
    assert leftovers(error) == [
        {"kind": "issue", "id": "issue-1", "state": "created"},
        {"kind": "event", "id": None, "state": "uncertain"},
    ]
    assert ("delete", "issue-1") not in issues.calls


# Step 3: summary storage


def test_definite_storage_failure_deletes_event_then_issue(
    workflow: ScheduledIssueWorkflow,
    issues: FakeIssues,
    calendar: FakeCalendar,
    store: FakeStore,
) -> None:
    store.error = SummaryStorageError("SECRET", may_have_applied=False, retryable=True)

    error = run(workflow)

    assert (error.code, error.step, error.retryable) == (
        ErrorCode.PROVIDER_ERROR,
        "summary",
        True,
    )
    assert "SECRET" not in error.message
    assert error.leftovers == []
    assert calendar.calls[-1] == ("delete", "event-1")
    assert issues.calls[-1] == ("delete", "issue-1")


def test_storage_not_configured_is_unavailable(
    workflow: ScheduledIssueWorkflow, store: FakeStore
) -> None:
    store.error = SummaryStorageError("x", may_have_applied=False, configured=False)

    error = run(workflow)

    assert (error.code, error.status) == (ErrorCode.PROVIDER_UNAVAILABLE, 503)
    assert error.leftovers == []


def test_storage_cleanup_failure_reports_each_leftover(
    workflow: ScheduledIssueWorkflow,
    issues: FakeIssues,
    calendar: FakeCalendar,
    store: FakeStore,
) -> None:
    store.error = SummaryStorageError("x", may_have_applied=False, retryable=True)
    calendar.delete_error = CalendarError(
        ErrorCode.PROVIDER_UNAVAILABLE, "later", retryable=True
    )
    issues.delete_error = IssueServiceError(IssueErrorCode.PROVIDER_ERROR, "x")

    error = run(workflow)

    assert error.retryable is False
    assert leftovers(error) == [
        {"kind": "event", "id": "event-1", "state": "created"},
        {"kind": "issue", "id": "issue-1", "state": "created"},
    ]


def test_uncertain_storage_keeps_issue_and_event(
    workflow: ScheduledIssueWorkflow,
    issues: FakeIssues,
    calendar: FakeCalendar,
    store: FakeStore,
) -> None:
    store.error = SummaryStorageError("x", may_have_applied=True)

    error = run(workflow)

    assert (error.code, error.step, error.retryable) == (
        ErrorCode.PROVIDER_ERROR,
        "summary",
        False,
    )
    assert leftovers(error) == [
        {"kind": "issue", "id": "issue-1", "state": "created"},
        {"kind": "event", "id": "event-1", "state": "created"},
        {"kind": "summary", "id": None, "state": "uncertain"},
    ]
    assert [call[0] for call in calendar.calls] == ["create"]
    assert [call[0] for call in issues.calls] == ["create"]


# HTTP error shape and logging


def test_http_failure_reports_step_and_leftovers_once(
    client: TestClient,
    calendar: FakeCalendar,
    caplog: pytest.LogCaptureFixture,
) -> None:
    calendar.create_error = CalendarError(
        ErrorCode.PROVIDER_ERROR, "unconfirmed SECRET", retryable=False
    )

    with caplog.at_level(logging.INFO, logger="calendar_service"):
        response = client.post(PATH, json=PAYLOAD)

    assert response.status_code == 502
    assert response.json() == {
        "error": {
            "code": "provider_error",
            "message": "Calendar event creation could not be confirmed. "
            "Check the calendar and issue tracker before retrying.",
            "retryable": False,
            "step": "event",
            "leftovers": [
                {"kind": "issue", "id": "issue-1", "state": "created"},
                {"kind": "event", "id": None, "state": "uncertain"},
            ],
        }
    }
    records = [json.loads(record.getMessage()) for record in caplog.records]
    assert len(records) == 1
    assert records[0]["operation"] == "create_scheduled_issue"
    assert records[0]["error"] == "provider_error"
    assert "SECRET" not in caplog.text
    assert "Fix login bug" not in caplog.text


# Default dependency wiring


def test_unconfigured_storage_fails_before_any_write(
    issues: FakeIssues,
    calendar: FakeCalendar,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def controlled_issues() -> IssueProvider:
        return issues

    def controlled_calendar() -> CalendarService:
        return calendar

    from app.calendar_service_dependencies import get_calendar_service

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_workflow_issue_provider] = controlled_issues
    app.dependency_overrides[get_calendar_service] = controlled_calendar
    try:
        response = TestClient(app).post(PATH, json=PAYLOAD)
    finally:
        app.dependency_overrides = previous

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "provider_unavailable",
        "message": "The summary storage is not configured or unavailable.",
        "retryable": False,
    }
    assert issues.calls == calendar.calls == []


def test_unconfigured_issue_tracker_fails_before_any_write(
    calendar: FakeCalendar, store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ISSUE_TRACKER_BASE_URL", raising=False)

    def controlled_calendar() -> CalendarService:
        return calendar

    def controlled_store() -> SummaryStore:
        return store

    from app.calendar_service_dependencies import get_calendar_service

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_calendar_service] = controlled_calendar
    app.dependency_overrides[get_summary_store] = controlled_store
    try:
        response = TestClient(app).post(PATH, json=PAYLOAD)
    finally:
        app.dependency_overrides = previous

    assert response.status_code == 503
    assert response.json()["error"]["message"] == (
        "The issue tracker is not configured or unavailable."
    )
    assert calendar.calls == store.saved == []


def test_openapi_documents_workflow() -> None:
    operation = app.openapi()["paths"][PATH]["post"]

    assert set(operation["responses"]) >= {"201", "403", "422", "502", "503"}
