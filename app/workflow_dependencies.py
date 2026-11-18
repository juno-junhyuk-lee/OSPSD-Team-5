"""Select the providers the scheduled-issue workflow composes.

Each dependency fails with a WorkflowError before any write when its
integration is not configured, so the workflow never starts half-wired. The
error's step names the affected integration. The shared Calendar dependency
raises CalendarError instead; WorkflowRoute translates it the same way.
"""

from collections.abc import Generator
from contextlib import ExitStack
from typing import Annotated

from calendar_contract import CalendarService
from fastapi import Depends
from issue_tracker_contract import IssueProvider
from issue_tracker_contract import ServiceError as IssueServiceError

from app.calendar_service_dependencies import get_calendar_service
from app.issue_tracker_dependencies import get_issue_provider
from app.storage_package import package_summary_store
from app.summary_storage import SummaryStorageError, SummaryStore
from app.workflow import ScheduledIssueWorkflow, not_configured


def get_workflow_issue_provider() -> Generator[IssueProvider, None, None]:
    """Reuse Member 3's factory; translate its configuration error."""
    dependency = get_issue_provider()
    try:
        provider = next(dependency)
    except IssueServiceError:
        raise not_configured("issue tracker", "issue") from None
    try:
        yield provider
    finally:
        dependency.close()


def get_summary_store() -> Generator[SummaryStore, None, None]:
    """Construct package storage before writes and close its SDK after the request."""
    with ExitStack() as stack:
        try:
            store = stack.enter_context(package_summary_store())
        except SummaryStorageError:
            raise not_configured("summary storage", "summary") from None
        # Only construction failures are configuration errors, not operation errors.
        yield store


def get_scheduled_issue_workflow(
    issues: Annotated[IssueProvider, Depends(get_workflow_issue_provider)],
    calendar: Annotated[CalendarService, Depends(get_calendar_service)],
    summaries: Annotated[SummaryStore, Depends(get_summary_store)],
) -> ScheduledIssueWorkflow:
    return ScheduledIssueWorkflow(issues=issues, calendar=calendar, summaries=summaries)
