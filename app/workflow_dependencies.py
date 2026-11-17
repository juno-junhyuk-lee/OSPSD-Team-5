"""Select the providers the scheduled-issue workflow composes.

Each dependency fails with a public ServiceError before any write when its
integration is not configured, so the workflow never starts half-wired.
"""

from collections.abc import Generator
from contextlib import ExitStack
from typing import Annotated

from calendar_contract import CalendarService
from fastapi import Depends
from issue_tracker_contract import IssueProvider
from issue_tracker_contract import ServiceError as IssueServiceError

from app.calendar_service_dependencies import get_calendar_service
from app.errors import ErrorCode, ServiceError
from app.issue_tracker_dependencies import get_issue_provider
from app.storage_package import package_summary_store
from app.summary_storage import SummaryStorageError, SummaryStore
from app.workflow import OPERATION, ScheduledIssueWorkflow, WorkflowError


def _not_configured(integration: str) -> ServiceError:
    return ServiceError(
        ErrorCode.PROVIDER_UNAVAILABLE,
        f"The {integration} is not configured or unavailable.",
        operation=OPERATION,
        retryable=False,
        provider=False,
    )


def get_workflow_issue_provider() -> Generator[IssueProvider, None, None]:
    """Reuse Member 3's factory; translate its configuration error."""
    dependency = get_issue_provider()
    try:
        provider = next(dependency)
    except IssueServiceError:
        raise _not_configured("issue tracker") from None
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
            raise WorkflowError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "The summary storage is not configured or unavailable.",
                step="summary",
                leftovers=[],
                retryable=False,
                provider=False,
            ) from None
        # Only construction failures are configuration errors, not operation errors.
        yield store


def get_scheduled_issue_workflow(
    issues: Annotated[IssueProvider, Depends(get_workflow_issue_provider)],
    calendar: Annotated[CalendarService, Depends(get_calendar_service)],
    summaries: Annotated[SummaryStore, Depends(get_summary_store)],
) -> ScheduledIssueWorkflow:
    return ScheduledIssueWorkflow(issues=issues, calendar=calendar, summaries=summaries)
