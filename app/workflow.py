"""Compose issue creation, Calendar scheduling, and a stored Markdown summary.

Order: issue -> event -> summary. Every input is validated before the first
write. A later step that fails definitively triggers best-effort deletion of
earlier writes (newest first). Uncertain writes are never retried or undone;
the error reports what may remain so the caller can reconcile.
"""

import re
from dataclasses import dataclass
from typing import Literal

from calendar_contract import CalendarError, CalendarService, CreateEvent, Event
from fastapi import Request
from fastapi.responses import JSONResponse
from issue_tracker_contract import ErrorCode as IssueErrorCode
from issue_tracker_contract import Issue, IssueCreate, IssueProvider
from issue_tracker_contract import ServiceError as IssueServiceError
from pydantic import BaseModel, ConfigDict, ValidationError

from app.errors import ErrorCode, ErrorDetails, ServiceError, log_failure
from app.observability import record_failure
from app.summary_storage import StoredSummary, SummaryStorageError, SummaryStore

OPERATION = "create_scheduled_issue"

Step = Literal["validate", "issue", "event", "summary"]
ResourceKind = Literal["issue", "event", "summary"]
ResourceState = Literal["created", "uncertain"]


class ScheduledIssueRequest(BaseModel):
    """One title is used for both the issue and the Calendar event."""

    model_config = ConfigDict(extra="forbid", strict=True)

    title: str
    start: str
    end: str


class SummaryDocument(BaseModel):
    id: str
    markdown: str


class ScheduledIssue(BaseModel):
    issue: Issue
    event: Event
    summary: SummaryDocument


class Leftover(BaseModel):
    """A resource that may still exist after a failed workflow."""

    kind: ResourceKind
    id: str | None
    state: ResourceState


class WorkflowError(ServiceError):
    """A ServiceError that names the failed step and anything left behind."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        step: Step,
        retryable: bool,
        provider: bool,
        leftovers: list[Leftover] | None = None,
    ) -> None:
        super().__init__(
            code,
            message,
            operation=OPERATION,
            retryable=retryable,
            provider=provider,
        )
        self.step = step
        self.leftovers = leftovers or []


@dataclass
class _Failure:
    code: ErrorCode
    message: str
    retryable: bool
    provider: bool
    uncertain: bool


_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>~])")


def escape_markdown(text: str) -> str:
    """Render untrusted text literally on one line."""
    one_line = " ".join(text.split())
    return _MARKDOWN_SPECIAL.sub(r"\\\1", one_line)


def render_summary(issue: Issue, event: Event) -> str:
    """Build the stored Markdown summary from provider-confirmed values."""
    return (
        f"# {escape_markdown(event.title)}\n"
        "\n"
        "| Field | Value |\n"
        "| --- | --- |\n"
        f"| Issue ID | `{_code_span(issue.id)}` |\n"
        f"| Issue title | {escape_markdown(issue.title)} |\n"
        f"| Event ID | `{_code_span(event.id)}` |\n"
        f"| Start | {escape_markdown(event.start)} |\n"
        f"| End | {escape_markdown(event.end)} |\n"
    )


def _code_span(value: str) -> str:
    # IDs are opaque; keep them inside one code span and one table cell.
    return " ".join(value.split()).replace("`", "'").replace("|", "\\|")


def summary_name(issue: Issue, event: Event) -> str:
    """A filesystem- and URL-safe name; storage may still assign its own ID."""
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", f"{issue.id}-{event.id}")
    return f"scheduled-issue-{safe[:200]}.md"


class ScheduledIssueWorkflow:
    def __init__(
        self,
        *,
        issues: IssueProvider,
        calendar: CalendarService,
        summaries: SummaryStore,
    ) -> None:
        self.issues = issues
        self.calendar = calendar
        self.summaries = summaries

    def run(self, request: ScheduledIssueRequest) -> ScheduledIssue:
        event_request = self._validate(request)

        try:
            issue = self.issues.create_issue(request.title)
        except IssueServiceError as error:
            failure = _issue_failure(error)
            raise self._fail(
                "issue",
                failure,
                [Leftover(kind="issue", id=None, state="uncertain")]
                if failure.uncertain
                else [],
            ) from None

        try:
            event = self.calendar.create(event_request)
        except CalendarError as error:
            failure = _calendar_failure(error)
            leftovers = [Leftover(kind="issue", id=issue.id, state="created")]
            if failure.uncertain:
                leftovers.append(Leftover(kind="event", id=None, state="uncertain"))
            else:
                leftovers = self._undo(issue=issue)
            raise self._fail("event", failure, leftovers) from None

        markdown = render_summary(issue, event)
        try:
            stored = self.summaries.save_summary(summary_name(issue, event), markdown)
        except SummaryStorageError as error:
            failure = _storage_failure(error)
            if failure.uncertain:
                leftovers = [
                    Leftover(kind="issue", id=issue.id, state="created"),
                    Leftover(kind="event", id=event.id, state="created"),
                    Leftover(kind="summary", id=None, state="uncertain"),
                ]
            else:
                leftovers = self._undo(issue=issue, event=event)
            raise self._fail("summary", failure, leftovers) from None

        return ScheduledIssue(
            issue=issue,
            event=event,
            summary=_summary_document(stored, markdown),
        )

    @staticmethod
    def _validate(request: ScheduledIssueRequest) -> CreateEvent:
        try:
            IssueCreate(title=request.title)
            return CreateEvent(
                title=request.title, start=request.start, end=request.end
            )
        except ValidationError:
            raise WorkflowError(
                ErrorCode.INVALID_INPUT,
                "Invalid request. Title must be 1-256 characters with a "
                "non-space character; start and end must be RFC 3339 times "
                "with end after start.",
                step="validate",
                retryable=False,
                provider=False,
            ) from None

    def _undo(self, *, issue: Issue, event: Event | None = None) -> list[Leftover]:
        """Delete earlier writes newest first; report any that could not be."""
        leftovers: list[Leftover] = []
        if event is not None:
            try:
                self.calendar.delete(event.id)
            except CalendarError as error:
                if error.code != ErrorCode.NOT_FOUND:
                    leftovers.append(
                        Leftover(kind="event", id=event.id, state="created")
                    )
        try:
            self.issues.delete_issue(issue.id)
        except IssueServiceError as error:
            if error.code != IssueErrorCode.NOT_FOUND:
                leftovers.append(Leftover(kind="issue", id=issue.id, state="created"))
        return leftovers

    @staticmethod
    def _fail(
        step: Step, failure: _Failure, leftovers: list[Leftover]
    ) -> WorkflowError:
        return WorkflowError(
            failure.code,
            failure.message,
            step=step,
            # Retrying is only safe when nothing from this attempt remains.
            retryable=failure.retryable and not leftovers,
            provider=failure.provider,
            leftovers=leftovers,
        )


class WorkflowErrorDetails(ErrorDetails):
    step: Step
    leftovers: list[Leftover]


class WorkflowErrorResponse(BaseModel):
    error: WorkflowErrorDetails


def workflow_error_handler(request: Request, error: Exception) -> JSONResponse:
    """Render the shared error fields plus the failed step and leftovers."""
    assert isinstance(error, WorkflowError)
    if not record_failure(request.scope, error.code, error.provider):
        log_failure(error)
    body = WorkflowErrorResponse(
        error=WorkflowErrorDetails(
            code=error.code,
            message=error.message,
            retryable=error.retryable,
            step=error.step,
            leftovers=error.leftovers,
        )
    )
    return JSONResponse(status_code=error.status, content=body.model_dump(mode="json"))


def _summary_document(stored: StoredSummary, markdown: str) -> SummaryDocument:
    return SummaryDocument(id=stored.id, markdown=markdown)


def _issue_failure(error: IssueServiceError) -> _Failure:
    provider = error.provider_involved
    if error.may_have_applied or error.code == IssueErrorCode.REQUEST_IN_PROGRESS:
        return _Failure(
            ErrorCode.PROVIDER_ERROR,
            "Issue creation could not be confirmed. "
            "Check the issue tracker before retrying.",
            retryable=False,
            provider=provider,
            uncertain=True,
        )
    mapped = {
        IssueErrorCode.INVALID_INPUT: (
            ErrorCode.INVALID_INPUT,
            "The issue tracker rejected the title.",
        ),
        IssueErrorCode.ACCESS_DENIED: (
            ErrorCode.ACCESS_DENIED,
            "The issue tracker denied access.",
        ),
        IssueErrorCode.SERVICE_NOT_CONFIGURED: (
            ErrorCode.PROVIDER_UNAVAILABLE,
            "The issue tracker is not configured or unavailable.",
        ),
    }
    code, message = mapped.get(
        error.code, (ErrorCode.PROVIDER_ERROR, "The issue tracker request failed.")
    )
    return _Failure(code, message, retryable=False, provider=provider, uncertain=False)


def _calendar_failure(error: CalendarError) -> _Failure:
    provider = error.code != ErrorCode.INVALID_INPUT
    if error.details is not None and isinstance(error.details.get("provider"), bool):
        provider = bool(error.details["provider"])
    # The shared contract reports uncertain writes as non-retryable PROVIDER_ERROR.
    if error.code == ErrorCode.PROVIDER_ERROR and not error.retryable:
        return _Failure(
            ErrorCode.PROVIDER_ERROR,
            "Calendar event creation could not be confirmed. "
            "Check the calendar and issue tracker before retrying.",
            retryable=False,
            provider=provider,
            uncertain=True,
        )
    messages = {
        ErrorCode.INVALID_INPUT: "The calendar rejected the event.",
        ErrorCode.ACCESS_DENIED: "The calendar denied permission to create the event.",
        ErrorCode.PROVIDER_UNAVAILABLE: "The calendar is temporarily unavailable.",
    }
    if error.code not in messages:
        return _Failure(
            ErrorCode.PROVIDER_ERROR,
            "The calendar request failed.",
            retryable=error.retryable,
            provider=provider,
            uncertain=False,
        )
    return _Failure(
        error.code,
        messages[error.code],
        retryable=error.retryable,
        provider=provider,
        uncertain=False,
    )


def _storage_failure(error: SummaryStorageError) -> _Failure:
    if error.may_have_applied:
        return _Failure(
            ErrorCode.PROVIDER_ERROR,
            "Summary storage could not be confirmed. The issue and event were kept.",
            retryable=False,
            provider=True,
            uncertain=True,
        )
    if not error.configured:
        return _Failure(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "Summary storage is not configured or unavailable.",
            retryable=False,
            provider=False,
            uncertain=False,
        )
    return _Failure(
        ErrorCode.PROVIDER_ERROR,
        "Summary storage failed.",
        retryable=error.retryable,
        provider=True,
        uncertain=False,
    )
